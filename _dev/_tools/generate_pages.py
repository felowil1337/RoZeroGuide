#!/usr/bin/env python3
"""Generate HTML pages from the extracted JSON data.

Outputs (in repo root):
- items.html             — all items grouped by source section
- items-md-equip.html    — Memorial Dungeon equipment by grade
- items-mats.html        — consumables / materials
- monster.html           — monster database grouped by dungeon
- skills.html            — skill database with per-level data
- crafting.html          — crafting recipes by grade

Each page is written with a nav placeholder; run `_dev/_tools/inject_nav.py`
afterwards to insert the canonical sidebar.

Re-runnable: existing pages are overwritten. Hand-edit only after generation
is finalized for the data, or extend this generator.
"""
from __future__ import annotations

import html as html_lib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EXTRACT = ROOT / "_dev" / "_working" / "criatura-extracted"
NAV_PLACEHOLDER = '<aside class="sidebar"></aside>'  # inject_nav.py will fill it

# ── helpers ──────────────────────────────────────────────────────────────
def esc(s: str | None) -> str:
    return html_lib.escape(s or "")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def local_icon(kro_id: str | None, kind: str, fallback_url: str | None) -> str:
    """Return path to local icon, falling back to remote URL if missing."""
    if not kro_id:
        return fallback_url or ""
    candidates = []
    if kind == "items":
        candidates = [f"images/equip/{kro_id}.png", f"images/items/{kro_id}.png"]
    elif kind == "monsters":
        candidates = [f"images/monsters/{kro_id}.png", f"images/monsters/{kro_id}.gif"]
    elif kind == "maps":
        candidates = [f"images/maps/{kro_id}.bmp", f"images/maps/{kro_id}.png"]
    for c in candidates:
        if (ROOT / c).exists():
            return c
    return fallback_url or ""


def page_template(title: str, eyebrow: str, lead: str, body: str, *, future: bool = False) -> str:
    hero_cls = " future" if future else ""
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)} — Ragnarok Zero Global Guide</title>
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
    <div class="page-hero{hero_cls}">
      <span class="eyebrow">{esc(eyebrow)}</span>
      <h1>{esc(title)}</h1>
      <p class="lead">{lead}</p>
    </div>

{body}

  </main>
</div>

<footer class="footer">
  Datenbasis: <a href="https://old.criatura-academy.com/" target="_blank" rel="noopener">Criatura Academy</a> ·
  Item-/Monster-IDs verlinken auf <a href="https://divine-pride.net/" target="_blank" rel="noopener">Divine Pride</a> für Detail-Daten.
</footer>

</body>
</html>
"""


# ── card renderers ───────────────────────────────────────────────────────
SET_LABELS = {
    "Subjugation (Grade IV) Equipment": ("Subjugation Set (Grade IV)", "subjugation-grade-iv-equipment"),
    "Expedition Equipment (Grade III)": ("Expedition Set (Grade III)", "expedition-equipment-grade-iii"),
    "Dispatching Equipment (Grade II)": ("Dispatching Set (Grade II)", "dispatching-equipment-grade-ii"),
    "Conqueror Equipment (Grade I)":   ("Conqueror Set (Grade I)",    "conqueror-equipment-grade-i"),
    "Hard Mode Accessories":           ("Hard-Mode Accessoires",       "hard-mode-accessories"),
}


def render_item_card(it: dict, *, link_target: bool = True) -> str:
    name = it.get("name_en") or "?"
    name_clean = re.sub(r"\s*\[\d+\]\s*$", "", name)
    slot_match = re.search(r"\[(\d+)\]", name)
    slot_html = f' <span class="entry-slot">[{slot_match.group(1)}]</span>' if slot_match else ""
    kro_id = it.get("kro_id") or ""
    icon = local_icon(kro_id, "items", it.get("icon_url"))
    type_label = it.get("type") or "Item"
    dp_url = f"https://divine-pride.net/database/item/{kro_id}" if kro_id else ""

    # Set-membership line (top-of-body banner)
    set_html = ""
    sec = it.get("source_section")
    if sec and sec in SET_LABELS:
        label, anchor = SET_LABELS[sec]
        set_html = (
            f'<div class="entry-set-line">'
            f'🔗 Teil von <a href="items-md-equip.html#sec-{anchor}">{esc(label)}</a>'
            f'</div>'
        )

    meta_lines: list[str] = []
    if it.get("crafted_from"):
        target_id = ""
        meta_lines.append(f'<li><strong>Crafted From:</strong> {esc(it["crafted_from"])}</li>')
    if it.get("drop_sources"):
        parts = []
        for d in it["drop_sources"]:
            slug_or_name = d.get("dungeon_slug") or slug(d.get("dungeon_name", ""))
            label = d.get("dungeon_name") or (d.get("dungeon_slug") or "?").replace("-", " ").title()
            mode = d.get("mode")
            mode_html = f' <span class="mode-badge {mode}">{mode}</span>' if mode and mode != "unknown" else ""
            qty = f' ({esc(d.get("qty"))})' if d.get("qty") else ""
            parts.append(f'<a href="instanzen.html#{slug_or_name}">{esc(label)}</a>{mode_html}{qty}')
        meta_lines.append(f'<li><strong>Drop:</strong> {" · ".join(parts)}</li>')
    weight_def = []
    if it.get("weight") is not None: weight_def.append(f'<strong>Gewicht:</strong> {it["weight"]}')
    if it.get("def") is not None:    weight_def.append(f'<strong>DEF:</strong> {it["def"]}')
    if weight_def:
        meta_lines.append(f'<li>{" · ".join(weight_def)}</li>')

    stats_html = ""
    if it.get("stats_raw"):
        stats_html = '<ul class="entry-stats">' + "".join(
            f"<li>{esc(s)}</li>" for s in it["stats_raw"]
        ) + "</ul>"

    name_inner = f'{esc(name_clean)}{slot_html}'
    name_link = (
        f'<a class="entry-name" href="{dp_url}" target="_blank" rel="noopener">{name_inner}</a>'
        if dp_url and link_target else f'<span class="entry-name">{name_inner}</span>'
    )

    foot = (
        f'<div class="entry-card-foot"><span>kRO #{esc(kro_id)}</span>'
        f'<a href="{dp_url}" target="_blank" rel="noopener">Divine Pride ↗</a></div>'
    ) if kro_id else ""

    icon_html = f'<img class="entry-icon" src="{esc(icon)}" alt="{esc(name)}" loading="lazy">' if icon else ""

    meta_html = f'<ul class="entry-meta">{"".join(meta_lines)}</ul>' if meta_lines else ""

    return f"""<div class="entry-card" id="item-{esc(kro_id)}">
  <div class="entry-card-head">
    {icon_html}
    {name_link}
    <span class="entry-type">{esc(type_label)}</span>
  </div>
  {set_html}
  {meta_html}
  {stats_html}
  {foot}
</div>"""


def render_monster_card(mon: dict) -> str:
    name = mon.get("name_en") or "?"
    kro_id = mon.get("kro_id") or ""
    icon = local_icon(kro_id, "monsters", mon.get("icon_url"))
    is_boss = (mon.get("class_type") or "").lower() == "boss"
    type_label = "Boss" if is_boss else (mon.get("class_type") or "Mob")
    dp = f"https://divine-pride.net/database/monster/{kro_id}" if kro_id else ""

    meta = []
    def push(label, val):
        if val not in (None, ""):
            meta.append(f'<li><strong>{label}:</strong> {esc(str(val))}</li>')
    push("Level", mon.get("level"))
    push("HP", f'{mon["hp"]:,}'.replace(",", ".") if mon.get("hp") else None)
    if mon.get("def") is not None or mon.get("mdef") is not None:
        push("DEF / MDEF", f'{mon.get("def","?")} / {mon.get("mdef","?")}')
    push("Familie", mon.get("family"))
    push("Element", mon.get("property"))
    push("Größe", mon.get("size"))
    if mon.get("exp_base") or mon.get("exp_job"):
        push("EXP / JEXP", f'{mon.get("exp_base") or "?"} / {mon.get("exp_job") or "?"}')

    icon_html = f'<img class="entry-icon" src="{esc(icon)}" alt="{esc(name)}" loading="lazy">' if icon else ""
    name_link = f'<a class="entry-name" href="{dp}" target="_blank" rel="noopener">{esc(name)}</a>' if dp else f'<span class="entry-name">{esc(name)}</span>'
    foot = f'<div class="entry-card-foot"><span>kRO #{esc(kro_id)}</span><a href="{dp}" target="_blank" rel="noopener">Divine Pride ↗</a></div>' if kro_id else ""

    return f"""<div class="entry-card is-monster" id="mob-{esc(kro_id)}">
  <div class="entry-card-head">
    {icon_html}
    {name_link}
    <span class="entry-type">{esc(type_label)}</span>
  </div>
  <ul class="entry-meta">{"".join(meta)}</ul>
  {foot}
</div>"""


def render_recipe_card(r: dict) -> str:
    name = r.get("name_en") or "?"
    kro_id = r.get("kro_id") or ""
    icon = local_icon(kro_id, "items", r.get("icon_url"))
    dp = f"https://divine-pride.net/database/item/{kro_id}" if kro_id else ""
    icon_html = f'<img class="entry-icon" src="{esc(icon)}" alt="{esc(name)}" loading="lazy">' if icon else ""

    mat_lines = []
    for m in r.get("materials", []):
        mid = m.get("kro_id") or ""
        micon = local_icon(mid, "items", m.get("icon_url"))
        mqty = m.get("qty") or ""
        mname = m.get("name_en") or "?"
        href = f"items.html#item-{mid}" if mid else "#"
        img_tag = f'<img src="{esc(micon)}" alt="" loading="lazy">' if micon else ""
        mat_lines.append(
            f'<a class="item-ref" href="{href}">{img_tag}'
            f'<span class="qty">{esc(str(mqty))}×</span>{esc(mname)}</a>'
        )
    mats_html = '<div style="padding:8px 12px;display:flex;flex-wrap:wrap;gap:4px;">' + " ".join(mat_lines) + "</div>" if mat_lines else ""
    name_link = f'<a class="entry-name" href="items.html#item-{esc(kro_id)}">{esc(name)}</a>' if kro_id else f'<span class="entry-name">{esc(name)}</span>'
    foot_html = f'<div class="entry-card-foot"><a href="{dp}" target="_blank" rel="noopener">Divine Pride ↗</a></div>' if dp else ""

    return f"""<div class="entry-card is-recipe">
  <div class="entry-card-head">
    {icon_html}
    {name_link}
    <span class="entry-type">Rezept</span>
  </div>
  {mats_html}
  {foot_html}
</div>"""


# ── data loading ─────────────────────────────────────────────────────────
def load_items() -> list[dict]:
    items = []
    for f in (EXTRACT / "items").glob("*.json"):
        if f.name.startswith("_"): continue
        items.append(json.loads(f.read_text()))
    items.sort(key=lambda x: int(x["kro_id"]) if x.get("kro_id", "").isdigit() else 0)
    return items


def load_monsters() -> list[dict]:
    mons = []
    for f in (EXTRACT / "monsters").glob("*.json"):
        if f.name.startswith("_"): continue
        mons.append(json.loads(f.read_text()))
    mons.sort(key=lambda x: x.get("level") or 0)
    return mons


def load_dungeons() -> list[dict]:
    dgs = []
    for f in (EXTRACT / "memorial-dungeons").glob("*.json"):
        dgs.append(json.loads(f.read_text()))
    return dgs


def load_recipes() -> list[dict]:
    return json.loads((EXTRACT / "crafting" / "recipes.json").read_text())


def load_skills() -> list[dict]:
    out = []
    for f in (EXTRACT / "skills").glob("*.json"):
        if f.name.startswith("_"): continue
        out.append(json.loads(f.read_text()))
    out.sort(key=lambda x: x.get("title", ""))
    return out


def load_quests() -> list[dict]:
    out = []
    for f in (EXTRACT / "quests").glob("*.json"):
        if f.name.startswith("_"): continue
        d = json.loads(f.read_text())
        if not d.get("is_hub"):
            out.append(d)
    out.sort(key=lambda x: x.get("title", ""))
    return out


def npc_local_icon(sprite_url: str | None, npc_name: str) -> str:
    """Try local copy of NPC sprite by name slug; fall back to remote URL."""
    if not sprite_url:
        return ""
    name_slug = re.sub(r"[^a-z0-9_]+", "_", (npc_name or "").lower()).strip("_")
    # Try slug-named files
    for ext in (".png", ".gif", ".jpg"):
        p = ROOT / "images" / "npcs" / f"{name_slug}{ext}"
        if p.exists():
            return f"images/npcs/{name_slug}{ext}"
    # Fall back to original URL filename
    fname = sprite_url.rsplit("/", 1)[-1]
    p = ROOT / "images" / "npcs" / fname
    if p.exists():
        return f"images/npcs/{fname}"
    return sprite_url


def quest_image_local(src: str, slug: str, idx: int) -> str:
    """Return path to a downloaded quest dialogue image, or remote URL fallback."""
    if not src:
        return ""
    fname = src.rsplit("/", 1)[-1]
    p = ROOT / "images" / "quests" / slug / fname
    if p.exists():
        return f"images/quests/{slug}/{fname}"
    return src


def render_quest_card(q: dict) -> str:
    title = q.get("title", q.get("slug", "?"))
    title_clean = re.sub(r"^Quest:\s*", "", title)
    slug_q = q.get("slug", "")
    parts = q.get("parts", [])
    part_blocks: list[str] = []
    for p in parts:
        # NPCs
        npc_html = ""
        for npc in p.get("npcs", []):
            sprite = npc_local_icon(npc.get("sprite_url"), npc.get("name", ""))
            sprite_tag = f'<img src="{esc(sprite)}" alt="{esc(npc.get("name",""))}" loading="lazy" style="width:40px;height:auto;vertical-align:middle;margin-right:8px;image-rendering:pixelated">' if sprite else ""
            navi = f' <code style="color:var(--accent);font-size:11px">/navi {npc["map"]} {npc["x"]}/{npc["y"]}</code>' if "map" in npc else ""
            npc_html += f'<div style="margin:4px 0">{sprite_tag}<strong>{esc(npc.get("name","?"))}</strong>{navi}</div>'

        # Rewards
        rewards = p.get("rewards") or {}
        rew_lines: list[str] = []
        if rewards.get("exp_base") is not None:
            rew_lines.append(f'<li><strong>Base-EXP:</strong> {rewards["exp_base"]:,}'.replace(",", ".") + '</li>')
        if rewards.get("exp_job") is not None:
            rew_lines.append(f'<li><strong>Job-EXP:</strong> {rewards["exp_job"]:,}'.replace(",", ".") + '</li>')
        for it in rewards.get("items", []):
            ref = f'<a href="items.html#item-{it["kro_id"]}">{esc(it["name_en"])}</a>' if it.get("kro_id") else esc(it.get("name_en", "?"))
            rew_lines.append(f'<li><strong>{it["qty"]}×</strong> {ref}</li>')
        for u in rewards.get("unlocks", []):
            rew_lines.append(f'<li><strong>Folge-Quest:</strong> {esc(u["quest"])}</li>')
        rew_html = f'<div style="padding:6px 12px"><strong style="font-size:12px;color:var(--text-dim)">Belohnung</strong><ul class="entry-stats">{"".join(rew_lines)}</ul></div>' if rew_lines else ""

        # Quest log (the in-game log text — what the game shows the player)
        log = p.get("quest_log") or {}
        log_html = ""
        if log.get("paragraphs"):
            paras = "".join(f'<p>{esc(t)}</p>' for t in log["paragraphs"])
            log_html = f'<div style="padding:8px 12px;background:rgba(95,168,255,0.06);border-left:2px solid var(--blue);margin:6px 12px"><strong style="font-size:12px;color:var(--blue)">📋 Quest-Log (im Spiel)</strong>{paras}</div>'

        # Dialogue / step-by-step walkthrough
        dlg_steps = p.get("dialogue") or []
        dlg_html = ""
        if dlg_steps:
            step_blocks = []
            for step in dlg_steps:
                step_label = step.get("step", "")
                step_texts = "".join(f'<p style="margin:4px 0;font-size:13px">{esc(t)}</p>' for t in step.get("texts", []))
                step_imgs = "".join(
                    f'<img src="{esc(quest_image_local(img["src"], slug_q, i))}" alt="{esc(img.get("alt",""))}" loading="lazy" style="max-width:100%;border-radius:4px;margin:4px 0">'
                    for i, img in enumerate(step.get("images", []))
                )
                step_blocks.append(
                    f'<div style="margin:8px 0;padding:6px 10px;border-left:2px solid var(--border-soft)">'
                    f'<div style="font-size:11px;font-weight:700;color:var(--accent);text-transform:uppercase">Schritt {esc(step_label)}</div>'
                    f'{step_imgs}{step_texts}</div>'
                )
            dlg_html = (
                '<details style="padding:8px 12px"><summary style="cursor:pointer;font-weight:600;font-size:13px">'
                f'📖 Komplette Dialog-Schritte ({len(dlg_steps)})</summary>'
                f'<div style="margin-top:8px">{"".join(step_blocks)}</div></details>'
            )

        part_blocks.append(f"""<div style="border-top:1px dashed var(--border-soft);padding:10px 12px 4px">
  <div style="font-weight:600;color:var(--accent);font-size:12px;text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px">{esc(p.get("label",""))}</div>
  {npc_html}
  {log_html}
  {rew_html}
  {dlg_html}
</div>""")

    foot = f'<div class="entry-card-foot"><a href="{esc(q.get("url",""))}" target="_blank" rel="noopener">criatura ↗</a></div>'
    return f"""<div class="entry-card" id="quest-{esc(slug_q)}">
  <div class="entry-card-head">
    <span class="entry-name">{esc(title_clean)}</span>
    <span class="entry-type">Quest</span>
  </div>
  {"".join(part_blocks)}
  {foot}
</div>"""


def _render_drop_grid_for_md(drops: list[dict]) -> str:
    """Render an item-card grid for an MD drop list. Each card is wrapped with
    a label strip showing the day-of-week prefix (Monday, Tuesday, …) and the
    drop quantity ranges (1-3 / 0-2 etc.)."""
    if not drops:
        return ""
    cards = []
    for d in drops:
        kid = d.get("kro_id")
        if not kid:
            continue
        item_path = EXTRACT / "items" / f"{kid}.json"
        if item_path.exists():
            full = json.loads(item_path.read_text())
            inner = render_item_card(full)
        else:
            inner = render_item_card(d)
        label_parts: list[str] = []
        if d.get("prefix"):
            label_parts.append(f'<span class="prefix">{esc(d["prefix"])}</span>')
        if d.get("qty_normal"):
            label_parts.append(f'<span class="qty"><span class="qty-l">N:</span>{esc(d["qty_normal"])}</span>')
        if d.get("qty_hard"):
            label_parts.append(f'<span class="qty"><span class="qty-l">H:</span>{esc(d["qty_hard"])}</span>')
        if d.get("note"):
            label_parts.append(f'<span class="note">★ {esc(d["note"])}</span>')
        if label_parts:
            cards.append(f'<div class="drop-wrap"><div class="drop-wrap-label">{"".join(label_parts)}</div>{inner}</div>')
        else:
            cards.append(inner)
    return f'<div class="entry-grid">{"".join(cards)}</div>'


# ── German translations of criatura's English MD-page text ──────────────
# Items, monsters, NPCs, map names, stats and game-mode names stay English by
# convention. Descriptive prose / section labels are translated.

MD_DE = {
    # Section labels
    "General Info":            "Allgemeine Infos",
    "Monster Info":            "Monster",
    "Treasure Chest Rewards":  "Schatztruhen-Belohnungen",
    "Possible enchants":       "Mögliche Enchant-Optionen",
    "Day of the week rewards": "Wochentag-Belohnungen",
    # Sections we keep English (game-system terms): Normal Mode, Hard Mode,
    # Headgear Enchant, Lower headgear, Consumables — game terminology

    # Intro paragraphs (one per MD)
    "This Memorial Dungeon is located in Orc Village (the map outside of Orc Dungeon). Speak to the Scientist NPC at the location marked with the arrow on the below map to start the instance.":
        "Diese Memorial-Dungeon liegt in Orc Village (die Map außerhalb des Orc Dungeon). Sprich mit dem Scientist-NPC an der mit dem Pfeil markierten Stelle, um die Instanz zu starten.",
    "This Memorial Dungeon is located on the map one west of Prontera at prt_fild05 264, 208. Speak with the Culvert Manager while in a party to start the instance.":
        "Diese Memorial-Dungeon liegt eine Map westlich von Prontera bei prt_fild05 264/208. Als Party mit dem Culvert Manager sprechen, um die Instanz zu starten.",
    "This Memorial Dungeon is located one map east of Prontera. Speak to the NPC a short distance from the entrance to get started, and then speak to the Dimensional Rift NPC next to her to enter.":
        "Diese Memorial-Dungeon liegt eine Map östlich von Prontera. Erst mit dem NPC kurz hinter dem Eingang sprechen, danach mit dem Dimensional-Rift-NPC daneben, um zu betreten.",
    "This Memorial Dungeon is located one map west of Prontera. Once on the map go in the 9 o' clock direction and speak with the NPC named Emily.":
        "Diese Memorial-Dungeon liegt eine Map westlich von Prontera. Auf der Map nach Westen (9-Uhr-Richtung) laufen und mit dem NPC Emily sprechen.",

    # Treasure-Chest intro paragraphs (multiple variants across MDs)
    "When you clear the dungeon, you are given a variety of rewards. Equipment drops increase when in a party of 7 or more people.":
        "Beim Clear erhältst du diverse Belohnungen. Equipment-Drops steigen mit einer Party von 7+ Spielern.",
    "When you clear the dungeon, you are given a variety of rewards. If the number of party members is 7 or more, a little more amount will be dropped. See the Memorial Dungeon Equipment Crafting page for":
        "Beim Clear erhältst du diverse Belohnungen. Mit 7+ Party-Mitgliedern droppt etwas mehr. Details siehe Memorial Dungeon Equipment Crafting page.",
    "When you clear the dungeon, you are given a variety of rewards. These include consumables, two lower head gear, and items that can be used to craft memorial dungeon equipment.":
        "Beim Clear erhältst du diverse Belohnungen — Consumables, zwei Lower-Headgear-Items und Materialien fürs Memorial Dungeon Equipment Crafting.",
    "If there are more members in your party, more reward items will drop.":
        "Mit mehr Party-Spielern droppen mehr Belohnungs-Items.",
    "Depending on the day of the week, you can get different Jello Fragments. These are used to craft Jello Stones, which in turn are used to craft higher-tier Memorial Dungeon equipment.":
        "Je nach Wochentag droppt ein anderes Jello Fragment. Daraus werden Jello Stones gecraftet, die wiederum für höherwertiges Memorial Dungeon Equipment gebraucht werden.",

    # General Info bullets
    "Must have a base level between 30 and 60 and be in a party to enter.":
        "Base-Level 30–60 und Party erforderlich, um zu betreten.",
    "Must have a base level of at least 59 to enter.":
        "Base-Level 59 oder höher erforderlich.",
    "Must have a base level of at least 70 to enter.":
        "Base-Level 70 oder höher erforderlich.",
    "Must have a base level of at least 80 to enter.":
        "Base-Level 80 oder höher erforderlich.",
    "Must have a base level of at least 99 to enter.":
        "Base-Level 99 oder höher erforderlich.",
    "Throughout the dungeon there are blue pillars. Clicking on them will transform you and give you increased ATK for a certain period of time.":
        "Im ganzen Dungeon stehen blaue Säulen. Anklicken transformiert dich und gibt für eine kurze Zeit ATK-Boost.",
    "You can access this memorial dungeon once a day, with the restriction resetting at 4AM.":
        "Diese Memorial-Dungeon ist 1×/Tag betretbar, Reset um 4 AM Server-Zeit.",
    "When battling the final boss, don't ignore the Shaman's Flowers, as they buff the boss.":
        "Beim Final-Boss die Shaman's Flowers nicht ignorieren — sie buffen den Boss.",
    "Several pieces of the Grade IV Memorial Dungeon Equipment can be found here.":
        "Mehrere Grade-IV-Memorial-Dungeon-Equipment-Teile droppen hier.",
    "To clear the dungeon, you must stop the toxic fuming geysers and kill the boss Maya.":
        "Zum Clear: die giftigen Geysire stoppen und den Boss Maya töten.",
    "See the Memorial Dungeon Equipment Crafting page for what to do with the items that drop in this instance.":
        "Was mit den gedroppten Items zu tun ist, steht auf der Memorial Dungeon Equipment Crafting page.",
    "As you kill monsters in this instance, the other monsters become stronger.":
        "Mit jedem getöteten Monster in dieser Instanz werden die übrigen Monster stärker.",
    "Be sure to kill all the Thief Bug Eggs to properly clear the dungeon. Initially, killing all the Thief Bug Eggs will spawn the Boss. Before killing the Boss, be":
        "Töte alle Thief Bug Eggs für einen sauberen Clear. Das Töten aller Eggs spawnt den Boss. Vor dem Boss-Kill:",
    "Stormy Drake's power increases according to the surrounding conditions during dungeon progression.":
        "Stormy Drake wird mit dem Dungeon-Fortschritt stärker, abhängig von Umgebungsbedingungen.",
    "To clear the dungeon smoothly, you must proceed carefully so that Stormy Drake doesn't become stronger.":
        "Für einen sauberen Clear vorsichtig vorgehen, damit Stormy Drake nicht zu stark wird.",
    "When clearing Sunken Ship, Stormy Mimic appears with a certain probability, and you can get an additonal treasure chest when you defeat all of them. This treasu":
        "Beim Sunken-Ship-Clear erscheinen mit gewisser Wahrscheinlichkeit Stormy Mimics. Werden alle besiegt, gibt es eine Bonus-Schatztruhe.",

    # Lower-headgear / enchant bullets
    "Wearable by all classes.": "Tragbar von allen Klassen.",
    "No slot.": "Kein Slot.",
    "Your character must be at least base level 30 to wear this headgear.":
        "Mindest-Base-Level 30, um die Headgear zu tragen.",
    "Can be enchanted.": "Enchantbar.",
    "Weight: 10": "Gewicht: 10",
    "Increase your movement speed while transformed. This does not stack with Increase Agility.":
        "Erhöht die Bewegungsgeschwindigkeit im Transform-Zustand. Stackt nicht mit Increase Agility.",
    "Use 50 Jellopy & 20,000 zeny to enchant the Poring Village Leek or Poring Village Carrot.":
        "50× Jellopy + 20.000 Zeny um Poring Village Leek oder Poring Village Carrot zu enchanten.",
    "Only one enchant can be added to an item.": "Nur ein Enchant pro Item möglich.",
    "30% chance of enchant failure.": "30 % Fehlschlagrate beim Enchant.",
    "Resetting an enchant costs 20,0000 zeny.": "Enchant-Reset kostet 200.000 Zeny.",
    "30% chance of resetting failure.": "30 % Fehlschlagrate beim Reset.",
    "If enchanting or resetting fails, the item is destroyed. *Added 2018.02.27":
        "Bei Fehlschlag (Enchant oder Reset) wird das Item zerstört.",

    # Stat bullets — kept tidy (drop the original game terms in EN)
    "STR +1": "STR +1", "AGI +1": "AGI +1", "VIT +1": "VIT +1",
    "INT +1": "INT +1", "DEX +1": "DEX +1", "LUK +1": "LUK +1",
    "SP +10": "SP +10", "SP +25": "SP +25",
    "SP +50 *Added 2018.02.27": "SP +50",
    "HP +100 *Changed 2018.02.27 (originally was +50)": "HP +100",
    "HP +200 *Changed 2018.02.27 (originally was +100)": "HP +200",
    "CRIT +1 *Removed in 2018.02.27": "CRIT +1 (entfernt)",
}


def de(text: str) -> str:
    """Look up the German translation; fall back to original if not in MD_DE."""
    return MD_DE.get(text.strip(), text)


# Auto-link rules: replace plain text mentions with hyperlinks to the right wiki page
AUTO_LINK_RULES = [
    (re.compile(r"\bMemorial Dungeon Equipment Crafting page\b", re.I),
     '<a href="crafting.html">Memorial-Dungeon-Equipment-Crafting</a>'),
    (re.compile(r"\bMemorial Dungeon Equipment\b(?! Crafting)", re.I),
     '<a href="items-md-equip.html">Memorial-Dungeon-Equipment</a>'),
    (re.compile(r"\bMemorial Dungeon\b(?! Equipment)", re.I),
     '<a href="instanzen.html">Memorial-Dungeon</a>'),
    (re.compile(r"\b(higher-tier|higher tier) Memorial Dungeon equipment\b", re.I),
     'höherwertiges <a href="items-md-equip.html">Memorial-Dungeon-Equipment</a>'),
]


def _autolink(text: str) -> str:
    """Apply AUTO_LINK_RULES to *already-escaped* text. Run after esc()."""
    for pat, repl in AUTO_LINK_RULES:
        text = pat.sub(repl, text)
    return text


def _render_md_image(src: str, slug: str, alt: str = "") -> str:
    """Render an image with local-file resolution where possible."""
    if not src:
        return ""
    fname = src.rsplit("/", 1)[-1]
    candidates = [
        ROOT / "images" / "maps" / fname,
        ROOT / "images" / "maps" / f"{slug}{Path(fname).suffix}",
        ROOT / "images" / "monsters" / fname,
        ROOT / "images" / "items" / fname,
        ROOT / "images" / "equip" / fname,
    ]
    local = None
    for c in candidates:
        if c.exists():
            local = str(c.relative_to(ROOT))
            break
    used = local or src
    return f'<img src="{esc(used)}" alt="{esc(alt)}" loading="lazy" style="max-width:100%;border:1px solid var(--border);border-radius:6px;background:var(--bg-1);padding:6px;margin:8px 0">'


def _render_md_section(sec: dict, slug: str, level: int = 2) -> str:
    """Render one parsed MD section (paragraphs / bullets / monsters / items /
    drops / images / subsections) into HTML. Recursive — subsections nest one
    heading level deeper. English text is run through the German translator."""
    h_tag = f"h{level}"
    parts: list[str] = [f"<{h_tag}>{esc(de(sec['label']))}</{h_tag}>"]

    for p in sec.get("paragraphs", []):
        parts.append(f"<p>{_autolink(esc(de(p)))}</p>")

    if sec.get("bullets"):
        parts.append(
            "<ul>" + "".join(f"<li>{_autolink(esc(de(b)))}</li>" for b in sec["bullets"]) + "</ul>"
        )

    if sec.get("monsters"):
        regular = [m for m in sec["monsters"] if (m.get("class_type") or "").lower() != "boss"]
        bosses  = [m for m in sec["monsters"] if (m.get("class_type") or "").lower() == "boss"]
        if regular:
            parts.append(f"<h{level+1}>Reguläre Mobs</h{level+1}>")
            parts.append('<div class="entry-grid wide">')
            parts.extend(render_monster_card(m) for m in regular)
            parts.append('</div>')
        if bosses:
            parts.append(f"<h{level+1}>Boss{'e' if len(bosses)>1 else ''}</h{level+1}>")
            parts.append('<div class="entry-grid wide">')
            parts.extend(render_monster_card(b) for b in bosses)
            parts.append('</div>')

    # Items section (non-drop item cards e.g. Poring Village Leek/Carrot)
    if sec.get("items"):
        parts.append(f"<h{level+1}>Items aus dieser Sektion</h{level+1}>")
        parts.append('<div class="entry-grid">')
        parts.extend(render_item_card(it) for it in sec["items"])
        parts.append('</div>')

    if sec.get("drops"):
        parts.append(_render_drop_grid_for_md(sec["drops"]))

    for img in sec.get("images") or []:
        parts.append(_render_md_image(img.get("src"), slug, img.get("alt", "")))

    for sub in sec.get("subsections") or []:
        parts.append(_render_md_section(sub, slug, level=min(level + 1, 6)))

    return "\n".join(parts)


def build_md_detail(md: dict) -> str:
    """One detail page per Memorial Dungeon — walks every parsed section so
    page covers everything criatura had (intro, general info, monsters, rewards
    sub-sections like Consumables / Day-of-week / Headgear-Enchant, etc.)."""
    slug = md["slug"]
    title = md.get("title_en") or slug.replace("-", " ").title()
    title_clean = re.sub(r"\s*Memorial Dungeon\s*$", "", title)

    # Intro paragraphs (between H1 and first H2)
    intro_html = ""
    if md.get("intro_paragraphs"):
        paras = "".join(f"<p>{_autolink(esc(de(p)))}</p>" for p in md["intro_paragraphs"])
        intro_html = f'<section class="md-intro">{paras}</section>'

    # Map image (if separate from sections)
    map_html = ""
    if md.get("map_image"):
        map_html = f'<section><h2>🗺️ Karte</h2>{_render_md_image(md["map_image"], slug, f"{title} map")}</section>'

    # Walk every parsed section
    section_html_parts: list[str] = []
    for sec in md.get("sections", []):
        section_html_parts.append(f'<section>{_render_md_section(sec, slug, level=2)}</section>')
    sections_html = "\n".join(section_html_parts)

    body = f"""    <div class="entry-jump">
      <a href="instanzen.html#{esc(slug)}">← zurück zu Memorial-Dungeons (deutscher Guide)</a>
      <a href="items-md-equip.html">🛡️ Memorial-Set-Items</a>
      <a href="crafting.html">🔨 Crafting-Rezepte</a>
      <a href="monster.html#dg-{esc(slug)}">👾 Mob-DB</a>
    </div>

    {intro_html}
    {map_html}
    {sections_html}
"""
    lead = f"Vollständige Daten zur Instanz <strong>{esc(title_clean)}</strong>: Lage, Eintritts-Voraussetzungen, Mob-Stats, Boss-Daten und alle Drop-Tabellen mit Stats."
    return page_template(title_clean, "Memorial-Dungeon · Detail", lead, body)


def build_quests() -> str:
    quests = load_quests()
    cards = "\n".join(render_quest_card(q) for q in quests)
    body = f"""    <section>
      <h2>{len(quests)} Quest-Walkthroughs</h2>
      <p>Pre-Trans-Quest-Übersicht mit NPC-Standorten (per <code>/navi</code>-Befehl), Reward-EXP und Item-Belohnungen. Die eigentlichen In-Game-Dialoge sind nicht abgedruckt — die liest du direkt im Spiel beim NPC.</p>
      <div class="entry-grid wide">
{cards}
      </div>
    </section>"""
    lead = "Quest-Datenbank für die ersten Pre-Trans-Quests in Izlude und auf Shipwreck Island. NPC-Standorte als <code>/navi</code>-Befehl, Belohnungen mit kRO-Item-IDs verlinkt zur Item-Datenbank."
    return page_template("Quest-Walkthroughs", "Quests · Pre-Trans", lead, body)


# ── page builders ────────────────────────────────────────────────────────
def build_items_all() -> str:
    items = load_items()
    by_section: dict[str, list[dict]] = {}
    for it in items:
        sec = it.get("source_section") or "Materialien & Sonstiges"
        by_section.setdefault(sec, []).append(it)

    # Quick-jump
    jumps = "".join(f'<a href="#sec-{slug(s)}">{esc(s)} ({len(items_)})</a>' for s, items_ in by_section.items())
    sections_html = []
    for sec, items_ in by_section.items():
        cards = "\n".join(render_item_card(it) for it in items_)
        sections_html.append(f"""    <section id="sec-{slug(sec)}">
      <h2>{esc(sec)}</h2>
      <div class="entry-grid">
{cards}
      </div>
    </section>""")
    body = f"""    <div class="entry-jump">{jumps}</div>
{"".join(sections_html)}"""

    lead = (
        f"Vollständige Item-Übersicht — {len(items)} Einträge mit Stats, Drop-Quellen und Crafting-Pfaden. "
        "Item-Namen bleiben Englisch (Spielsprache). Klick aufs Icon öffnet Divine Pride mit den Originaldaten."
    )
    return page_template("Item-Datenbank", "Items · Alle Einträge", lead, body)


def build_items_md_equip() -> str:
    items = [i for i in load_items() if i.get("source_section") and "Equipment" in i["source_section"] or i.get("source_section", "").startswith("Hard Mode")]
    if not items:
        # Fallback: include everything that has a known type
        items = [i for i in load_items() if i.get("type") and i["type"] not in ("unknown", None)]
    by_section: dict[str, list[dict]] = {}
    for it in items:
        sec = it.get("source_section") or "Sonstige"
        by_section.setdefault(sec, []).append(it)
    jumps = "".join(f'<a href="#sec-{slug(s)}">{esc(s)}</a>' for s in by_section)
    secs = []
    for sec, items_ in by_section.items():
        cards = "\n".join(render_item_card(it) for it in items_)
        secs.append(f"""    <section id="sec-{slug(sec)}">
      <h2>{esc(sec)}</h2>
      <div class="entry-grid">
{cards}
      </div>
    </section>""")
    body = f"""    <div class="entry-jump">{jumps}</div>
{"".join(secs)}"""
    lead = "Memorial-Dungeon-Equipment in vier Grades (IV → I) plus Hard-Mode-Accessoires. Höhere Grades werden aus dem niedrigeren Grad gecraftet — siehe <a href=\"crafting.html\">Crafting</a>."
    return page_template("Memorial-Set Equipment", "Items · Memorial-Set", lead, body)


def build_items_mats() -> str:
    items = [i for i in load_items() if not i.get("source_section") or i.get("source_section", "").startswith(("Materialien", "Sonstige"))]
    # Also include items without a section that aren't equipment
    if not items:
        items = [i for i in load_items() if not (i.get("type") and "Equipment" in (i.get("source_section") or ""))]
    cards = "\n".join(render_item_card(it) for it in items)
    body = f"""    <section>
      <h2>Materialien & Verbrauchsgegenstände</h2>
      <p>Diese Items fallen in den Memorial-Dungeons (oder werden für Crafting/Enchanting benötigt) und stehen in keinem festen Equipment-Slot.</p>
      <div class="entry-grid">
{cards}
      </div>
    </section>"""
    lead = f"{len(items)} Materialien und Verbrauchsgegenstände aus den Memorial-Dungeons. Verwendung im <a href=\"crafting.html\">Crafting</a> und <a href=\"enchant-system.html\">Enchanting</a>."
    return page_template("Materialien & Verbrauchsgegenstände", "Items · Materialien", lead, body)


def build_monster_db() -> str:
    mons = load_monsters()
    dgs = load_dungeons()
    # group by dungeon (a monster can appear in multiple)
    dg_title = {d["slug"]: d["title_en"] for d in dgs}
    mons_by_dg: dict[str, list[dict]] = {}
    for m in mons:
        for ap in m.get("appears_in") or []:
            mons_by_dg.setdefault(ap["dungeon_slug"], []).append(m)
    jumps = "".join(f'<a href="#dg-{esc(s)}">{esc(dg_title.get(s, s))}</a>' for s in mons_by_dg)
    secs = []
    for slug_, mlist in mons_by_dg.items():
        cards = "\n".join(render_monster_card(m) for m in mlist)
        secs.append(f"""    <section id="dg-{esc(slug_)}">
      <h2>{esc(dg_title.get(slug_, slug_))}</h2>
      <div class="entry-grid wide">
{cards}
      </div>
    </section>""")
    body = f"""    <div class="entry-jump">{jumps}</div>
{"".join(secs)}"""
    lead = f"{len(mons)} Monster aus den Memorial-Dungeons mit Level, HP, DEF/MDEF, Familie und Element. Bosse sind farblich markiert. Stats stammen aus kRO Zero — auf Global können einzelne Werte abweichen."
    return page_template("Monster-Datenbank", "Mobs · Memorial-Dungeons", lead, body)


def build_skills() -> str:
    skills = load_skills()
    cards: list[str] = []
    for sk in skills:
        title = sk.get("title") or sk.get("slug")
        f_ = sk.get("fields", {})
        meta = []
        for label, key in [("Max Level", "max_level"), ("Type", "type"), ("Kind", "skill_kind"),
                            ("Target", "target"), ("Prerequisite", "prerequisite")]:
            v = f_.get(key)
            if v: meta.append(f'<li><strong>{label}:</strong> {esc(v)}</li>')
        # Per-level grid
        lvls = sk.get("level_effects") or {}
        per_lists = sk.get("per_level_lists") or {}
        per_level_table = ""
        if lvls or per_lists:
            max_lv = max([int(k) for k in lvls.keys()] + [len(v) for v in per_lists.values()] + [0])
            if max_lv > 0:
                rows = ""
                header = "<tr><th>Lv</th><th>Effekt</th>"
                ord_keys = ["sp_cost", "fixed_casting", "variable_casting", "skill_cooldown", "global_cooldown"]
                for k in ord_keys:
                    if k in per_lists: header += f'<th>{esc(k.replace("_", " ").title())}</th>'
                header += "</tr>"
                for i in range(1, max_lv + 1):
                    row = f"<tr><td>{i}</td><td>{esc(lvls.get(str(i), ''))}</td>"
                    for k in ord_keys:
                        if k in per_lists:
                            arr = per_lists[k]
                            row += f'<td>{esc(arr[i-1]) if i-1 < len(arr) else ""}</td>'
                    row += "</tr>"
                    rows += row
                per_level_table = f'<div class="table-wrap" style="margin:8px 12px 12px"><table><thead>{header}</thead><tbody>{rows}</tbody></table></div>'
        cards.append(f"""<div class="entry-card is-skill" id="skill-{esc(sk['slug'])}">
  <div class="entry-card-head">
    <span class="entry-name">{esc(title)}</span>
    <span class="entry-type">Skill</span>
  </div>
  <ul class="entry-meta">{"".join(meta)}</ul>
  {per_level_table}
  <div class="entry-card-foot"><span><a href="{esc(sk.get("url", ""))}" target="_blank" rel="noopener">criatura ↗</a></span></div>
</div>""")
    body = f"""    <div class="info-box future" style="margin-bottom:20px">
      <strong>🔮 Trans-Klassen-Inhalt:</strong> Diese Skills gehören zu den Transcendent-Klassen (Lord Knight, High Wizard, Sniper) und sind im initialen Global-Release noch nicht verfügbar. Siehe <a href="trans-klassen.html">Trans-Klassen-Übersicht</a>.
    </div>

    <section>
      <h2>{len(skills)} Trans-Skills mit per-Level-Daten</h2>
      <p>SP-Kosten, Cast-Time und Cooldown pro Level. Werte aus kRO Zero — auf Global können einzelne Skills bei Release abweichen. Bei Abweichungen gilt die offizielle Patch-Note.</p>
      <div class="entry-grid single">
{"".join(cards)}
      </div>
    </section>"""
    lead = "Skill-Datenbank für Trans-Klassen-Skills (Lord Knight, High Wizard, Sniper) mit per-Level-Werten (SP-Kosten, Cast-Time, Cooldown)."
    return page_template("Trans-Skill-Datenbank", "Skills · Trans (Zukunft)", lead, body, future=True)


def build_crafting() -> str:
    recipes = load_recipes()
    by_grade: dict[str, list[dict]] = {}
    for r in recipes:
        sec = r.get("section") or "Sonstige"
        by_grade.setdefault(sec, []).append(r)
    jumps = "".join(f'<a href="#sec-{slug(s)}">{esc(s)} ({len(rs)})</a>' for s, rs in by_grade.items())
    secs = []
    for sec, rs in by_grade.items():
        cards = "\n".join(render_recipe_card(r) for r in rs)
        secs.append(f"""    <section id="sec-{slug(sec)}">
      <h2>{esc(sec)}</h2>
      <div class="entry-grid wide">
{cards}
      </div>
    </section>""")
    body = f"""    <div class="entry-jump">{jumps}</div>
{"".join(secs)}"""
    lead = (
        f"{len(recipes)} Memorial-Equipment-Rezepte. Höhere Grades werden aus dem jeweils niedrigeren Grad plus "
        "Crystal- und Jello-Stone-Materialien hergestellt. Crafting-NPCs siehe <a href=\"npc.html\">NPC-Übersicht</a>."
    )
    return page_template("Memorial-Equipment-Crafting", "Crafting · Memorial-Set", lead, body)


# ── driver ───────────────────────────────────────────────────────────────
def main() -> None:
    pages = {
        "items.html":          build_items_all(),
        "items-md-equip.html": build_items_md_equip(),
        "items-mats.html":     build_items_mats(),
        "monster.html":        build_monster_db(),
        "skills.html":         build_skills(),
        "crafting.html":       build_crafting(),
        "quests.html":         build_quests(),
    }
    # Per-MD detail pages — one per dungeon JSON
    for f in (EXTRACT / "memorial-dungeons").glob("*.json"):
        md = json.loads(f.read_text())
        pages[f"md-{md['slug']}.html"] = build_md_detail(md)
    for name, content in pages.items():
        path = ROOT / name
        path.write_text(content, encoding="utf-8")
        print(f"wrote {name}: {len(content):>7} bytes")

    # Pages are written with an empty <aside> placeholder. Inject the canonical
    # nav now so the generated pages aren't shipped with an empty sidebar.
    import subprocess, sys
    subprocess.run([sys.executable, str(ROOT / "_dev" / "_tools" / "inject_nav.py")], check=True)


if __name__ == "__main__":
    main()
