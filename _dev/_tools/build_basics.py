#!/usr/bin/env python3
"""Generate basics.html with stat tables, elemental matrix, and weapon-vs-size
table. Embeds the structured RO Zero / pre-renewal mechanic data inline so
basics.html is fully self-contained and reproducible.

Run after editing the embedded tables to regenerate the page. inject_nav.py
is invoked at the end so the sidebar is filled in.
"""
from __future__ import annotations

import html as html_lib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "basics.html"


def esc(s: str) -> str:
    return html_lib.escape(s or "")


# ── DATA ──────────────────────────────────────────────────────────────────

STATS = {
    "STR": {
        "tag": "Stärke — Melee-ATK & Tragelimit",
        "rows": [
            ("ATK (Melee)",       "+1 pro Punkt",    "floor(STR/10)² Bonus alle 10",     ""),
            ("ATK (Ranged)",      "kein Beitrag",    "—",                                "Ranged-Waffen nutzen DEX statt STR"),
            ("Trage-Limit",       "+30 pro Punkt",   "—",                                "Basis 20.000 + STR×30"),
        ],
    },
    "AGI": {
        "tag": "Agility — FLEE & Angriffsgeschwindigkeit",
        "rows": [
            ("FLEE",              "+1 pro Punkt",    "—",                                "Basis FLEE = BaseLvl + AGI"),
            ("ASPD",              "skaliert (Hauptbeitrag)", "(AGI×4 + DEX)/4 — waffenabhängig", "AGI dominanter Faktor"),
            ("Stun-Resist",       "+0,1 % pro Punkt", "+1 % pro 10",                     "Sekundär; primär VIT"),
        ],
    },
    "VIT": {
        "tag": "Vitality — Max-HP, DEF & Status-Resists",
        "rows": [
            ("Max-HP",            "+1 % der Job-Basis-HP", "—",                          "MaxHP = JobBaseHP × (1 + VIT/100)"),
            ("DEF (soft)",        "+1 pro Punkt",    "—",                                "Reduziert Schaden flach"),
            ("MDEF (soft)",       "+0,5 pro Punkt",  "+1 pro 2",                         "floor(VIT/2)"),
            ("HP-Regen",          "skaliert",        "—",                                "Tick = MaxHP/200 + VIT/5"),
            ("Status: Stun",      "+1 % pro Punkt",  "—",                                "100 VIT = immun"),
            ("Status: Poison",    "+1 % pro Punkt",  "—",                                "100 VIT = immun"),
            ("Status: Silence",   "+1 % pro Punkt",  "—",                                "100 VIT = immun"),
            ("Status: Blind",     "+0,7 % pro Punkt", "—",                               "Kombiniert mit INT"),
            ("Status: Bleeding",  "+1 % pro Punkt",  "—",                                ""),
            ("Heal-Effekt",       "+0,2 % erhalten", "+2 % pro 10",                      "Auf empfangene Heilung"),
        ],
    },
    "INT": {
        "tag": "Intelligence — Magie-Schaden, MDEF & SP",
        "rows": [
            ("MATK (Min)",        "+1 pro Punkt",    "floor(INT/7)² Bonus alle 10",      "MATK_min = INT + floor(INT/7)²"),
            ("MATK (Max)",        "+1 pro Punkt",    "floor(INT/5)² Bonus alle 10",      "MATK_max = INT + floor(INT/5)²"),
            ("Max-SP",            "+1 % der Basis-SP", "—",                              "MaxSP = JobBaseSP × (1 + INT/100)"),
            ("SP-Regen",          "skaliert",        "+1 pro 6",                         "Tick = MaxSP/100 + INT/6 (+1 ab 120)"),
            ("MDEF (hard)",       "+1 pro Punkt",    "—",                                "% Reduktion Magie-Schaden"),
            ("Status: Sleep",     "+1 % pro Punkt",  "—",                                "100 INT = immun"),
            ("Status: Blind",     "+0,3 % pro Punkt", "—",                               "Kombiniert mit VIT"),
            ("Status: Stone",     "+0,5 % pro Punkt", "—",                               ""),
        ],
    },
    "DEX": {
        "tag": "Dexterity — Ranged-ATK, HIT, Cast-Time",
        "rows": [
            ("ATK (Ranged)",      "+1 pro Punkt",    "floor(DEX/10)² Bonus alle 10",     "Wie STR für Melee"),
            ("ATK (Melee)",       "+0,2 pro Punkt",  "—",                                "floor(DEX/5) zusätzlich"),
            ("HIT",               "+1 pro Punkt",    "—",                                "Basis HIT = BaseLvl + DEX"),
            ("Variable Cast-Time","reduziert",       "—",                                "VCT = Basis × (1 - DEX/150) — 150 DEX = instant"),
            ("ASPD",              "minor",           "—",                                "~1/4 der Wirkung von AGI"),
            ("Min-ATK (Waffe)",   "skaliert",        "—",                                "Hebt Waffen-ATK-Floor"),
        ],
    },
    "LUK": {
        "tag": "Luck — Crit & Status-Resists",
        "rows": [
            ("Crit-Rate",         "+0,33 pro Punkt", "+1 pro 3",                         "Crit = 1 + LUK/3"),
            ("ATK",               "+0,2 pro Punkt",  "+1 pro 5",                         "floor(LUK/5)"),
            ("MATK",              "+0,33 pro Punkt", "+1 pro 3",                         "floor(LUK/3)"),
            ("HIT",               "+0,2 pro Punkt",  "+1 pro 5",                         "floor(LUK/5)"),
            ("Perfect Dodge",     "+0,1 pro Punkt",  "+1 pro 10",                        "Lucky Dodge = 1 + LUK/10"),
            ("Status: Curse",     "+1 % pro Punkt",  "—",                                ""),
            ("Status: Poison",    "+0,25 % pro Punkt","—",                               ""),
            ("Crit-Resistenz",    "−0,2 pro LUK",    "—",                                "Verteidiger LUK/5 senkt Angreifer-Crit"),
        ],
    },
}

ELEMENTS = ["Neutral", "Water", "Earth", "Fire", "Wind", "Poison", "Holy", "Shadow", "Ghost", "Undead"]

ELEMENT_MATRIX_BY_LEVEL = {
    1: {
        "Neutral": {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison": 100, "Holy": 100, "Shadow": 100, "Ghost":  25, "Undead": 100},
        "Water":   {"Neutral": 100, "Water":  90, "Earth": 100, "Fire": 150, "Wind":  90, "Poison": 100, "Holy": 100, "Shadow": 100, "Ghost":  25, "Undead": 100},
        "Earth":   {"Neutral": 100, "Water": 100, "Earth":  90, "Fire":  90, "Wind": 150, "Poison":  50, "Holy": 100, "Shadow": 100, "Ghost":  25, "Undead": 100},
        "Fire":    {"Neutral": 100, "Water": 150, "Earth":  50, "Fire":  90, "Wind": 100, "Poison": 100, "Holy": 100, "Shadow": 100, "Ghost":  25, "Undead": 100},
        "Wind":    {"Neutral": 100, "Water":  50, "Earth": 100, "Fire": 100, "Wind":  90, "Poison": 100, "Holy": 100, "Shadow": 100, "Ghost":  25, "Undead": 100},
        "Poison":  {"Neutral": 100, "Water": 100, "Earth":  50, "Fire": 100, "Wind": 100, "Poison":  25, "Holy": 100, "Shadow":  50, "Ghost":  25, "Undead":  50},
        "Holy":    {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison":  50, "Holy":   0, "Shadow": 125, "Ghost":  75, "Undead": 100},
        "Shadow":  {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison":  50, "Holy": 125, "Shadow":   0, "Ghost":  75, "Undead": 100},
        "Ghost":   {"Neutral":  25, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison": 100, "Holy":  75, "Shadow":  75, "Ghost": 125, "Undead": 100},
        "Undead":  {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 125, "Wind": 100, "Poison":   0, "Holy": 150, "Shadow": -25, "Ghost":  75, "Undead":   0},
    },
    2: {
        "Neutral": {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison": 100, "Holy": 100, "Shadow": 100, "Ghost":   0, "Undead": 100},
        "Water":   {"Neutral": 100, "Water":  75, "Earth": 100, "Fire": 175, "Wind":  80, "Poison": 100, "Holy": 100, "Shadow": 100, "Ghost":   0, "Undead": 100},
        "Earth":   {"Neutral": 100, "Water": 100, "Earth":  75, "Fire":  80, "Wind": 175, "Poison":  25, "Holy": 100, "Shadow": 100, "Ghost":   0, "Undead": 100},
        "Fire":    {"Neutral": 100, "Water": 175, "Earth":  25, "Fire":  75, "Wind": 100, "Poison": 100, "Holy": 100, "Shadow": 100, "Ghost":   0, "Undead": 100},
        "Wind":    {"Neutral": 100, "Water":  25, "Earth": 100, "Fire": 100, "Wind":  75, "Poison": 100, "Holy": 100, "Shadow": 100, "Ghost":   0, "Undead": 100},
        "Poison":  {"Neutral": 100, "Water": 100, "Earth":  25, "Fire": 100, "Wind": 100, "Poison":   0, "Holy": 100, "Shadow":  25, "Ghost":   0, "Undead":  25},
        "Holy":    {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison":  25, "Holy":   0, "Shadow": 150, "Ghost":  50, "Undead": 100},
        "Shadow":  {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison":  25, "Holy": 150, "Shadow":   0, "Ghost":  50, "Undead": 100},
        "Ghost":   {"Neutral":   0, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison": 100, "Holy":  50, "Shadow":  50, "Ghost": 150, "Undead": 100},
        "Undead":  {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 150, "Wind": 100, "Poison":   0, "Holy": 175, "Shadow": -50, "Ghost":  50, "Undead":   0},
    },
    3: {
        "Neutral": {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison": 100, "Holy": 100, "Shadow": 100, "Ghost": -25, "Undead": 100},
        "Water":   {"Neutral": 100, "Water":  50, "Earth": 100, "Fire": 200, "Wind":  70, "Poison": 100, "Holy": 100, "Shadow": 100, "Ghost": -25, "Undead": 100},
        "Earth":   {"Neutral": 100, "Water": 100, "Earth":  50, "Fire":  70, "Wind": 200, "Poison":   0, "Holy": 100, "Shadow": 100, "Ghost": -25, "Undead": 100},
        "Fire":    {"Neutral": 100, "Water": 200, "Earth":   0, "Fire":  50, "Wind": 100, "Poison": 100, "Holy": 100, "Shadow": 100, "Ghost": -25, "Undead": 100},
        "Wind":    {"Neutral": 100, "Water":   0, "Earth": 100, "Fire": 100, "Wind":  50, "Poison": 100, "Holy": 100, "Shadow": 100, "Ghost": -25, "Undead": 100},
        "Poison":  {"Neutral": 100, "Water": 100, "Earth":   0, "Fire": 100, "Wind": 100, "Poison": -25, "Holy": 100, "Shadow":   0, "Ghost": -25, "Undead":   0},
        "Holy":    {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison":   0, "Holy": -25, "Shadow": 175, "Ghost":  25, "Undead": 100},
        "Shadow":  {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison":   0, "Holy": 175, "Shadow": -25, "Ghost":  25, "Undead": 100},
        "Ghost":   {"Neutral": -25, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison": 100, "Holy":  25, "Shadow":  25, "Ghost": 175, "Undead": 100},
        "Undead":  {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 175, "Wind": 100, "Poison": -25, "Holy": 200, "Shadow": -75, "Ghost":  25, "Undead": -25},
    },
    4: {
        "Neutral": {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison": 100, "Holy": 100, "Shadow":  100, "Ghost": -50, "Undead": 100},
        "Water":   {"Neutral": 100, "Water":  25, "Earth": 100, "Fire": 200, "Wind":  60, "Poison": 100, "Holy": 100, "Shadow":  100, "Ghost": -50, "Undead": 100},
        "Earth":   {"Neutral": 100, "Water": 100, "Earth":  25, "Fire":  60, "Wind": 200, "Poison": -25, "Holy": 100, "Shadow":  100, "Ghost": -50, "Undead": 100},
        "Fire":    {"Neutral": 100, "Water": 200, "Earth": -25, "Fire":  25, "Wind": 100, "Poison": 100, "Holy": 100, "Shadow":  100, "Ghost": -50, "Undead": 100},
        "Wind":    {"Neutral": 100, "Water": -25, "Earth": 100, "Fire": 100, "Wind":  25, "Poison": 100, "Holy": 100, "Shadow":  100, "Ghost": -50, "Undead": 100},
        "Poison":  {"Neutral": 100, "Water": 100, "Earth": -25, "Fire": 100, "Wind": 100, "Poison": -50, "Holy": 100, "Shadow":  -25, "Ghost": -50, "Undead": -25},
        "Holy":    {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison": -25, "Holy": -50, "Shadow":  200, "Ghost":   0, "Undead": 100},
        "Shadow":  {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison": -25, "Holy": 200, "Shadow":  -50, "Ghost":   0, "Undead": 100},
        "Ghost":   {"Neutral": -50, "Water": 100, "Earth": 100, "Fire": 100, "Wind": 100, "Poison": 100, "Holy":   0, "Shadow":    0, "Ghost": 200, "Undead": 100},
        "Undead":  {"Neutral": 100, "Water": 100, "Earth": 100, "Fire": 200, "Wind": 100, "Poison": -50, "Holy": 200, "Shadow": -100, "Ghost":   0, "Undead": -50},
    },
}

WEAPON_SIZE = [
    ("Bare Hand (Knuckle)", 100, 100, 100),
    ("Dagger",              100,  75,  50),
    ("One-Handed Sword",     75, 100,  75),
    ("Two-Handed Sword",     75,  75, 100),
    ("One-Handed Spear",     75, 100, 100),
    ("Two-Handed Spear",     50, 100, 100),
    ("One-Handed Axe",       50,  75, 100),
    ("Two-Handed Axe",       50,  75, 100),
    ("Mace",                 75, 100, 100),
    ("Two-Handed Mace",      75, 100, 100),
    ("Bow",                 100, 100,  75),
    ("Staff (1H / 2H)",     100, 100, 100),
    ("Book",                100, 100,  50),
    ("Whip",                 75, 100,  75),
    ("Musical Instrument",   75, 100,  75),
    ("Katar",                75, 100,  75),
    ("Revolver",            100, 100,  75),
    ("Rifle",                75, 100, 100),
    ("Shotgun",              75, 100, 100),
    ("Gatling Gun",         100, 100,  75),
    ("Grenade Launcher",     75, 100, 100),
]

ZERO_NOTES = [
    "RO Zero verwendet Pre-Renewal-Formeln (multiplikativer Card-Mod, Soft+Hard-DEF-Split, Pre-Renewal-MATK).",
    "Cast-Time ist vollständig variabel (kein Fixed-Cast-Anteil) — 150 DEX = instant.",
    "ASPD nutzt die Pre-Renewal-Waffen-Delay-Tabelle.",
    "HP/SP-Skalierung: JobBaseHP × (1 + VIT/100) bzw. JobBaseSP × (1 + INT/100) — multiplikativ, nicht additiv wie Renewal.",
    "Crit-Formel bleibt 1 + LUK/3; Verteidiger LUK/5 senkt Angreifer-Crit.",
    "Elementar-Matrix entspricht der Standard-Pre-Renewal-Lv1-Tabelle (Zero hat sie nicht modifiziert).",
    "Größen-Modifikatoren entsprechen Vanilla Pre-Renewal — Rebellion-Schusswaffen verwenden dasselbe Schema.",
    "Status-Resist-Werte nutzen lineare Pre-Renewal-Formeln — 100 % im Primär-Stat heißt Immunität.",
]


# ── HELPERS ───────────────────────────────────────────────────────────────

def elem_class(v: int) -> str:
    if v < 0:    return "elem-heal"
    if v == 0:   return "elem-immune"
    if v <= 25:  return "elem-strong-resist"
    if v <= 50:  return "elem-resist"
    if v <= 75:  return "elem-mild-resist"
    if v <= 95:  return "elem-near-neutral"
    if v <= 110: return "elem-neutral"
    if v <= 130: return "elem-mild-weak"
    if v <= 160: return "elem-weak"
    if v <= 180: return "elem-strong-weak"
    if v >= 200: return "elem-stronger"
    return "elem-strong-weak"


def render_stats() -> str:
    cards: list[str] = []
    for stat, info in STATS.items():
        rows_html = "".join(
            f"<tr><td><strong>{esc(eff)}</strong></td>"
            f"<td class=\"formula\">{esc(per_pt)}</td>"
            f"<td class=\"formula\">{esc(per_10)}</td>"
            f"<td class=\"note\">{esc(note)}</td></tr>"
            for eff, per_pt, per_10, note in info["rows"]
        )
        cards.append(
            f'<div class="stat-card">'
            f'  <div class="stat-card-head"><span class="stat-name">{stat}</span>'
            f'<span class="stat-tag">{esc(info["tag"])}</span></div>'
            f'  <table>'
            f'    <thead><tr><th>Effekt</th><th>Pro Punkt</th><th>Pro 10 (Bonus)</th><th>Anmerkung</th></tr></thead>'
            f'    <tbody>{rows_html}</tbody>'
            f'  </table>'
            f'</div>'
        )
    return f'<div class="stat-grid">{"".join(cards)}</div>'


def render_element_matrix() -> str:
    """Render four matrices (one per defender-element-level) as CSS-only tabs."""
    head = '<tr><th class="row-label">Verteidiger ↓ / Angreifer →</th>' + \
           "".join(f"<th>{e}</th>" for e in ELEMENTS) + '</tr>'

    panels = []
    for lv in (1, 2, 3, 4):
        matrix = ELEMENT_MATRIX_BY_LEVEL[lv]
        rows = []
        for defender in ELEMENTS:
            cells = "".join(
                f'<td class="{elem_class(matrix[defender][att])}">{matrix[defender][att]}</td>'
                for att in ELEMENTS
            )
            rows.append(f'<tr><th class="row-label">{defender}</th>{cells}</tr>')
        panels.append(
            f'<div class="elem-panel elem-{lv}" style="overflow-x:auto">'
            f'<table class="element-matrix">{head}{"".join(rows)}</table>'
            '</div>'
        )

    radios = "\n".join(
        f'<input type="radio" name="elv" id="elv{lv}" class="elem-tabs-input"{" checked" if lv == 1 else ""}>'
        for lv in (1, 2, 3, 4)
    )
    tabs = '<div class="elem-tabs">' + "".join(
        f'<label for="elv{lv}">Lv {lv} (Standard-Defender)</label>'
        if lv == 1 else
        f'<label for="elv{lv}">Lv {lv}</label>'
        for lv in (1, 2, 3, 4)
    ) + '</div>'

    return (
        f'{radios}\n'
        f'<div class="elem-wrap">{tabs}{"".join(panels)}</div>'
    )


def render_weapon_size() -> str:
    rows = "".join(
        f'<tr><td><strong>{esc(w)}</strong></td>'
        f'<td>{s} %</td><td>{m} %</td><td>{l} %</td></tr>'
        for w, s, m, l in WEAPON_SIZE
    )
    return (
        '<div class="table-wrap"><table>'
        '<thead><tr><th>Waffenklasse</th><th>Small</th><th>Medium</th><th>Large</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
    )


# ── PAGE TEMPLATE ─────────────────────────────────────────────────────────

PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Game Basics — RO Zero Guide</title>
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

  <main>
    <div class="page-hero">
      <span class="eyebrow">Pre-Renewal-Formeln · Einstieg</span>
      <h1>Game Basics</h1>
      <p class="lead">Stat-Effekte, Elementar-Tabelle und Waffen-vs-Größe-Modifikatoren — alles, was du für Build- und Schaden-Berechnungen brauchst. Plus: das in Zero integrierte MENU-Poring &amp; Hint-System für Einsteiger.</p>
    </div>

    <div class="entry-jump">
      <a href="#stats">📊 Stat-Effekte</a>
      <a href="#element">🌪️ Elementar-Tabelle</a>
      <a href="#waffen-groesse">⚔️ Waffe vs Monster-Größe</a>
      <a href="#zero-notes">📌 RO-Zero-Besonderheiten</a>
      <a href="#menu">🍑 MENU-Poring</a>
      <a href="#hint">💡 Hint-System</a>
    </div>

    <section id="stats">
      <h2>📊 Stat-Effekte (Pre-Renewal)</h2>
      <p>Jeder Stat-Punkt hat eine direkte Wirkung — und alle 10 Punkte gibt es zusätzlich einen quadratischen Bonus (z.B. STR-ATK-Bonus = floor(STR/10)²). Die Tabelle zeigt sowohl den Pro-Punkt-Beitrag als auch die Pro-10-Schwelle.</p>
{stats_html}
    </section>

    <section id="element">
      <h2>🌪️ Elementar-Modifikator-Tabelle (Lv 1)</h2>
      <p>Schadens-Multiplikator beim Treffen eines Verteidigers eines bestimmten Elements mit einer Waffe/Skill eines anderen Elements. <strong>Reihen = Verteidiger</strong>, <strong>Spalten = Angreifer</strong>. 100 % = neutral, &lt;100 = Resistenz, &gt;100 = Schwäche, 0 = immun, negativ = heilt.</p>

{matrix_html}

      <p class="muted">Wechsle zwischen den Tabs für die vier Defender-Element-Level. Lv 1 ist der Standard, Lv 4 das Maximum (z.B. „Fire-Lv-4-Defender" wie der Stormy Drake in Sunken Ship). Mit steigendem Level wird die Abweichung von 100&nbsp;% verstärkt.</p>

      <div class="info-box note">
        <strong>RO-Zero-spezifisch:</strong> Zero verwendet die Standard-Pre-Renewal-Element-Tabelle unverändert. Item-Effekte wie „Wind Armor +20 % Wind Resistance" werden <em>zusätzlich</em> angewendet — siehe <a href="items.html">Item-Datenbank</a> für Item-Modifikatoren.
      </div>
    </section>

    <section id="waffen-groesse">
      <h2>⚔️ Waffenklasse vs Monster-Größe</h2>
      <p>Pre-Renewal-Größenmodifikatoren — das Verhältnis von Waffen-ATK zu Monster-Größe (Small / Medium / Large). 100 % = voller Schaden, 75 % / 50 % = entsprechend reduziert.</p>

{weapon_html}

      <div class="info-box note">
        <strong>Tipp:</strong> Item-Effekte wie „Ignores size penalty" heben die Reduktion auf — bei <a href="items.html">Item-Datenbank</a> nachschauen, ob deine Waffe so einen Modifier hat.
      </div>
    </section>

    <section id="zero-notes">
      <h2>📌 RO-Zero-Besonderheiten</h2>
      <ul>
{zero_notes_html}
      </ul>
    </section>

    <section id="menu">
      <h2>🍑 MENU-Poring &amp; Hint-System</h2>
      <p>Zero hat keine klassische Tutorial-Overlay-Lösung, sondern ein jederzeit aufrufbares Hint-Panel — du entscheidest, wann und was du nachlesen willst. Hier die drei Schritte vom Login bis zur Hint-Übersicht:</p>

      <div class="card" id="step1" style="margin-bottom:16px">
        <h4>Schritt 1 — MENU (Pink Poring) öffnen</h4>
        <p>Nach dem Login findest du unten rechts das <strong>MENU-Icon</strong> in Form eines Pink Poring. Klick drauf und wähle dann die <strong>Hint-Box (Fragezeichen-Icon)</strong>.</p>
        <img src="images/basics/2025_05_20_67c6c53490854b97a5ba5608bf15b17a.png" alt="MENU-Poring und Hint-Icon in der UI" style="max-width:100%;border-radius:6px;border:1px solid var(--border);background:var(--bg-1);padding:6px;margin:8px 0">
        <details class="translated-table">
          <summary><strong>📋 Hauptmenü-Übersicht (deutsche Beschriftungen)</strong></summary>
          <p class="translated-summary">Das Bild zeigt das Hauptmenü-Interface mit Symbolen für die Spielsysteme — der rote Pfeil markiert den Hilfe-Button.</p>
          <ul>
            <li><strong>Character</strong> — Persönlicher Status</li>
            <li><strong>Equipment</strong> — Ausrüstung</li>
            <li><strong>Inventory</strong> — Inventar</li>
            <li><strong>Skills</strong> — Fertigkeiten</li>
            <li><strong>Party</strong> — Gruppe</li>
            <li><strong>Guild</strong> — Gilde</li>
            <li><strong>Quest Log</strong> — Aufgabenliste</li>
            <li><strong>World Map</strong> — Weltkarte</li>
            <li><strong>Navigation</strong> — Navigation</li>
            <li><strong>Options</strong> — Optionen</li>
            <li><strong>Bank</strong> — Bank</li>
            <li><strong>Replay</strong> — Wiedergabe</li>
            <li><strong>Mail</strong> — Post</li>
            <li><strong>Achievements</strong> — Erfolge</li>
            <li><strong>Cash Shop</strong> — Shop</li>
            <li><strong>Shortcut Guide</strong> — Tastenkürzel-Guide</li>
            <li><strong>Attendance</strong> — Anwesenheit</li>
            <li><strong>Recruitment Center</strong> — Vermittlungsstelle</li>
            <li><strong>Help</strong> — Hilfefenster</li>
            <li><strong>Auto Battle</strong> — Automatischer Kampf</li>
            <li><strong>Reputation</strong> — Ansehen</li>
          </ul>
          <p class="translated-notes">Der „MENU"-Button unten rechts schließt oder öffnet dieses Fenster.</p>
        </details>
      </div>

      <div class="card" id="step2" style="margin-bottom:16px">
        <h4>Schritt 2 — „Vorschlagsliste" aufrufen</h4>
        <p>Beim ersten Klick wird ein <strong>zufälliger Hint</strong> angezeigt. Um gezielt zu suchen, klickst du auf <strong>„Vorschlagsliste durchsuchen"</strong> — damit landest du auf der Übersichtsseite aller verfügbaren Hints.</p>
        <img src="images/basics/2025_05_20_b379e472f682491ea8c1572c00a9c351.png" alt="Hint-Vorschlagsliste mit Auto-Attack-Erklärung" style="max-width:100%;border-radius:6px;border:1px solid var(--border);background:var(--bg-1);padding:6px;margin:8px 0">
        <details class="translated-table">
          <summary><strong>📋 Hilfefenster: Auto-Attack (deutsche Übersetzung)</strong></summary>
          <p class="translated-summary">Ein Hilfefenster im Spiel, das erklärt, wie der Auto-Attack-Modus funktioniert.</p>
          <ul>
            <li><strong>Modus:</strong> Auto-Attack</li>
            <li><strong>Beschreibung:</strong> Wenn du beim Angriff auf ein Monster die <kbd>Strg</kbd>-Taste gedrückt hältst, wird der Auto-Attack-Modus aktiviert, bis das Monster besiegt ist. Klicken auf eine andere Stelle hebt den Modus auf.</li>
            <li><strong>Permanent-Modus:</strong> Bei Eingabe von <code>/noctrl</code> kann der Auto-Attack-Modus auch ohne Halten der Strg-Taste aktiviert werden. Erneutes <code>/noctrl</code> deaktiviert den Modus wieder.</li>
            <li><strong>Verwandt:</strong> Kampf → Angriff</li>
            <li><strong>Aktion:</strong> Vorschlagsliste durchsuchen</li>
          </ul>
          <p class="translated-notes">Das Fenster enthält außerdem Steuerelemente wie „Beim Start öffnen", „Schließen" und eine Seitenzahlanzeige (1/1).</p>
        </details>
      </div>

      <div class="card" id="step3" style="margin-bottom:16px">
        <h4>Schritt 3 — Hint-Startseite (Kategorien-Übersicht)</h4>
        <p>Von hier aus führen die Kategorien direkt zu den Themen, die dich interessieren — einfach anklicken und in die Tiefe gehen.</p>
        <img src="images/basics/2025_05_20_0f30d680e6db4eb2b4a093f3359844e8.png" alt="Hint-Startseite mit Kategorien" style="max-width:100%;border-radius:6px;border:1px solid var(--border);background:var(--bg-1);padding:6px;margin:8px 0">
        <details class="translated-table">
          <summary><strong>📋 Hilfemenü-Kategorien (deutsche Übersetzung)</strong></summary>
          <p class="translated-summary">Das In-Game-Hilfefenster mit Kategorien zum Spielablauf sowie eine Übersicht der Hauptmenü-Icons am unteren rechten Bildschirmrand.</p>
          <ul>
            <li><strong>Quest</strong> — Aufbau und Ablauf von Missionen</li>
            <li><strong>Combat</strong> — Grundlagen zu Kampf, Targeting und Cooldowns</li>
            <li><strong>Item</strong> — Itemtypen, Crafting, Handel</li>
            <li><strong>Game Options Window</strong> — UI, Hotkeys, Client-Verhalten</li>
            <li><strong>Remove Restriction Effects</strong> — Status-Effekte aufheben</li>
            <li><strong>Browse Recommended List</strong> — Vorschlagsliste durchsuchen</li>
            <li><strong>Inventory / Skill Window / Party / World Map / Navigation / Options</strong></li>
            <li><strong>Mail / Achievement System / Help / Cash Shop / Shortcut Guide / Attendance</strong></li>
            <li><strong>Brokerage</strong> — Vermittlungsstelle</li>
            <li><strong>Reputation</strong> — Ansehens-System</li>
            <li><strong>Auto Combat</strong> — Auto-Hunt (siehe <a href="auto-hunt.html">Auto-Hunt-Seite</a>)</li>
          </ul>
          <p class="translated-notes">Die Liste enthält die grundlegenden Spielfunktionen. Die Icons rechts stellen das zentrale Charakter- und System-Management dar.</p>
        </details>
      </div>

      <div class="info-box note">
        <strong>Hint-Inhalte werden per Patch erweitert</strong> — Änderungen der offiziellen Seite haben stets Vorrang gegenüber dieser Wiki-Seite.
      </div>
    </section>

    <section id="hint">
      <h2>💡 Praxis-Tipps</h2>
      <ul>
        <li><strong>Pflicht für Einsteiger:</strong> Combat- und Items-Sektionen klären viele Zero-Besonderheiten, die klassische RO-Veteranen überraschen können.</li>
        <li><strong>Auto-Attack:</strong> Strg-Halten beim Angriff aktiviert Auto-Attack auf das Ziel; <code>/noctrl</code> macht es permanent.</li>
        <li><strong>Daily-Tipp:</strong> Der erste Hint-Klick ist absichtlich randomisiert — gut als Mini-Info-Happen pro Login.</li>
        <li><strong>MENU bleibt im Kampf erreichbar</strong> — kein Tutorial-Overlay, sondern jederzeit aufrufbar.</li>
      </ul>
    </section>

  </main>
</div>

<footer class="footer">
  Datenbasis: <a href="https://wiki.playragnarokzero.com/" target="_blank" rel="noopener">Project Zero Wiki</a> · iRO Wiki · <a href="https://www.midgardhub.com/" target="_blank" rel="noopener">Midgard Hub</a> · Pre-Renewal-Formeln verifiziert gegen kRO Zero. Screenshots © Gravity / GNJOY TW.
</footer>

</body>
</html>
"""


def main() -> None:
    zero_notes_html = "\n".join(f"        <li>{esc(n)}</li>" for n in ZERO_NOTES)
    OUT.write_text(PAGE.format(
        stats_html=render_stats(),
        matrix_html=render_element_matrix(),
        weapon_html=render_weapon_size(),
        zero_notes_html=zero_notes_html,
    ), encoding="utf-8")
    print(f"wrote basics.html: {OUT.stat().st_size}b")
    subprocess.run([sys.executable, str(ROOT / "_dev" / "_tools" / "inject_nav.py")], check=True)


if __name__ == "__main__":
    main()
