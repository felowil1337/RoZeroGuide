#!/usr/bin/env python3
"""
Enrich items.html, items-md-equip.html and monster.html with data from the
criatura-extracted JSON dumps under _dev/_working/criatura-extracted/.

Idempotent: re-running the script makes no changes when the data is already
present.

Behaviour
---------
- Items: for every <div class="entry-card" id="item-<kROID>"> we look for the
  matching <kROID>.json under _dev/_working/criatura-extracted/items/.
  * If the JSON has stats_raw and the card has no <ul class="entry-stats">,
    a new <ul class="entry-stats"> is inserted right after the existing
    <ul class="entry-meta"> and the English stat lines are translated to
    German where straightforward.
  * If the entry-meta has no Gewicht/DEF/Slots data and the JSON provides
    them, an additional <li> is appended to the existing entry-meta.
- Monsters: for every <div class="entry-card ..." id="mob-<kROID>"> /
  id="monster-<kROID>"> we look for the matching <kROID>.json under
  _dev/_working/criatura-extracted/monsters/.
  * If no <ul class="entry-stats"> exists and the JSON has level/HP data,
    a consolidated stat block is inserted after the existing entry-meta.

Counters are printed at the end.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup, NavigableString
except ImportError:  # pragma: no cover
    print("BeautifulSoup is required (pip install beautifulsoup4)", file=sys.stderr)
    raise

ROOT = Path("/home/trusch/rozero")
ITEMS_JSON_DIR = ROOT / "_dev/_working/criatura-extracted/items"
MONSTERS_JSON_DIR = ROOT / "_dev/_working/criatura-extracted/monsters"
ITEMS_HTML = ROOT / "items.html"
ITEMS_MD_HTML = ROOT / "items-md-equip.html"
MONSTERS_HTML = ROOT / "monster.html"


# ---------------------------------------------------------------------------
# German translation helpers
# ---------------------------------------------------------------------------

# Whole-line replacements (set bonuses, etc.) -- these are the most common
# templates seen in the criatura data and benefit from a clean German
# rendering.  Anything that doesn't match these patterns falls through to
# substring replacements and finally to a plain English line.

_PHRASE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^If total Set is refined higher than \+(\d+):\s*", re.I),
     r"Wenn das gesamte Set über +\1 verbessert ist: "),
    (re.compile(r"^If total Set is refined higher than \+(\d+),?\s*", re.I),
     r"Wenn das gesamte Set über +\1 verbessert ist: "),
    (re.compile(r"^If refined higher than \+(\d+):\s*", re.I),
     r"Wenn über +\1 verbessert: "),
    (re.compile(r"^If refined higher than \+(\d+),?\s*", re.I),
     r"Wenn über +\1 verbessert: "),
    (re.compile(r"^For each refine level above \+(\d+):\s*", re.I),
     r"Pro Verbesserungsstufe über +\1: "),
    (re.compile(r"^When wearing\s+", re.I), "Mit "),
    (re.compile(r"^When equipped with\s+", re.I), "Mit "),
    (re.compile(r"^Wearing\s+", re.I), "Mit "),
    (re.compile(r"^Increases\s+", re.I), "Erhöht "),
    (re.compile(r"^Reduces\s+", re.I), "Reduziert "),
    (re.compile(r"^Decreases\s+", re.I), "Reduziert "),
    (re.compile(r"^Adds\s+", re.I), "Fügt "),
    (re.compile(r"^Enables\s+", re.I), "Aktiviert "),
]

# Inline replacements (whole words / short phrases). These are deliberately
# conservative: if a phrase is ambiguous it is left in English instead of
# guessing.
_SUBSTITUTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bgetragen worden\b", re.I), "getragen"),
    (re.compile(r"\b& \b"), "& "),
    (re.compile(r":\s*ATK\b"), ": ATK"),
    (re.compile(r"\bvariable casting\b", re.I), "variable Castzeit"),
    (re.compile(r"\bvariable cast time\b", re.I), "variable Castzeit"),
    (re.compile(r"\bfixed cast time\b", re.I), "fixe Castzeit"),
    (re.compile(r"\bcasting time\b", re.I), "Castzeit"),
    (re.compile(r"\bcast time\b", re.I), "Castzeit"),
    (re.compile(r"\bafter attack delay\b", re.I), "Nach-Angriffs-Delay"),
    (re.compile(r"\battack speed\b", re.I), "Angriffsgeschwindigkeit"),
    (re.compile(r"\bmovement speed\b", re.I), "Bewegungsgeschwindigkeit"),
    (re.compile(r"\bskill damage\b", re.I), "Skill-Schaden"),
    (re.compile(r"\bphysical damage\b", re.I), "physischen Schaden"),
    (re.compile(r"\bmagical damage\b", re.I), "magischen Schaden"),
    (re.compile(r"\bdamage to\b", re.I), "Schaden gegen"),
    (re.compile(r"\bdamage from\b", re.I), "Schaden von"),
    (re.compile(r"\bresistance\b", re.I), "Resistenz"),
    (re.compile(r"\brecovery\b", re.I), "Regeneration"),
    (re.compile(r"\brace\b", re.I), "Rasse"),
    (re.compile(r"\bproperty\b", re.I), "Element"),
    (re.compile(r"\bsize\b", re.I), "Größe"),
    (re.compile(r"\bsmall monsters?\b", re.I), "kleine Monster"),
    (re.compile(r"\bmedium monsters?\b", re.I), "mittlere Monster"),
    (re.compile(r"\blarge monsters?\b", re.I), "große Monster"),
    (re.compile(r"\bDemi[- ]?Human\b", re.I), "Demi-Human"),
    (re.compile(r"\benemies\b", re.I), "Gegner"),
    (re.compile(r"\benemy\b", re.I), "Gegner"),
    (re.compile(r"\bchance to\b", re.I), "Chance auf"),
    (re.compile(r"\bchance of\b", re.I), "Chance auf"),
    (re.compile(r"\bwhen attacking\b", re.I), "beim Angriff"),
    (re.compile(r"\bwhen attacked\b", re.I), "beim Angegriffenwerden"),
    (re.compile(r"\bwhen using\b", re.I), "beim Einsatz von"),
    (re.compile(r"\bwhen taking\b", re.I), "beim Erhalten von"),
    (re.compile(r"\bwhen receiving\b", re.I), "beim Erhalten von"),
    (re.compile(r"\bAuto-spell\b", re.I), "Auto-Spell"),
    (re.compile(r"\bAutospell\b", re.I), "Auto-Spell"),
    (re.compile(r"\beach refine level\b", re.I), "jede Verbesserungsstufe"),
    (re.compile(r"\brefine level\b", re.I), "Verbesserungsstufe"),
    (re.compile(r"\brefined\b", re.I), "verbessert"),
]


def translate_stat_line(line: str) -> str:
    """Best-effort English -> German rewrite of a single stat line.

    Game terms (item names, ATK, MATK, MDEF, ASPD, MaxHP, ...) and numeric
    values are preserved verbatim. The result still contains English
    fragments where a clean translation is non-trivial -- this is intentional
    (per the task spec: "honest English than confused German").
    """

    out = line.strip()
    for pattern, repl in _PHRASE_PATTERNS:
        new = pattern.sub(repl, out)
        if new != out:
            out = new
            break

    for pattern, repl in _SUBSTITUTIONS:
        out = pattern.sub(repl, out)

    return out


# ---------------------------------------------------------------------------
# JSON loading
# ---------------------------------------------------------------------------


def load_json_dir(directory: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not directory.is_dir():
        return out
    for path in directory.iterdir():
        if path.suffix.lower() != ".json":
            continue
        if path.stem.startswith("_"):
            continue
        try:
            out[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"WARN: cannot parse {path}: {exc}", file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


_NUMBER_FORMAT_THOUSANDS = re.compile(r"(?<=\d)(?=(\d{3})+(?!\d))")


def fmt_int(value: int | float | None) -> str | None:
    if value is None:
        return None
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return None
    s = str(ivalue)
    return _NUMBER_FORMAT_THOUSANDS.sub(".", s)


def meta_has_weight(meta_text: str) -> bool:
    return "gewicht" in meta_text.lower()


def meta_has_def(meta_text: str) -> bool:
    return "def:" in meta_text.lower()


def meta_has_slots(meta_text: str) -> bool:
    return "slot" in meta_text.lower()


def cleanup_duplicate_meta_li(meta_ul) -> int:
    """Remove duplicate Gewicht/DEF/Slots <li> entries inside an entry-meta UL.

    A <li> is considered a duplicate if every <strong>Label:</strong> value
    pair it contains is already present in an earlier sibling <li> (with the
    same value). The shorter / earlier <li> is kept; the duplicate is dropped.

    Returns the number of <li> elements removed.
    """
    label_re = re.compile(r"<strong>([^<]+):</strong>\s*([^·<]+?)(?=\s*·|\s*</li>|$)")

    def parse(li) -> dict[str, str]:
        html = li.decode_contents()
        out: dict[str, str] = {}
        for m in label_re.finditer(html):
            label = m.group(1).strip().lower()
            value = m.group(2).strip()
            if label in {"gewicht", "def", "slots"}:
                out[label] = value
        return out

    removed = 0
    seen: list[dict[str, str]] = []
    for li in list(meta_ul.find_all("li", recursive=False)):
        parsed = parse(li)
        if not parsed or not any(k in {"gewicht", "def", "slots"} for k in parsed):
            seen.append({})
            continue
        is_dup = False
        for prev in seen:
            if not prev:
                continue
            # Check if every label in `parsed` matches an entry in `prev`
            # OR if every label in `prev` matches one in `parsed` (i.e. one
            # is a subset of the other).
            if all(prev.get(k) == v for k, v in parsed.items()):
                is_dup = True
                break
            if all(parsed.get(k) == v for k, v in prev.items()) and len(parsed) > len(prev):
                # current contains all of prev, drop prev and keep current
                # (rare; happens when migration ran with the buggy version
                # adding a richer line first).
                # We do this by replacing prev with parsed conceptually --
                # safer: remove the previous matching <li> instead.
                for sib in list(meta_ul.find_all("li", recursive=False)):
                    if parse(sib) == prev:
                        sib.decompose()
                        removed += 1
                        break
                # Fix `seen` so the new (richer) li becomes the canonical one
                idx = seen.index(prev)
                seen[idx] = parsed
                is_dup = True  # don't re-add
                seen.append(parsed)
                break
        if is_dup:
            li.decompose()
            removed += 1
        else:
            seen.append(parsed)
    return removed


def enrich_items(html_path: Path, items_data: dict[str, dict]) -> tuple[int, int, int]:
    """Returns (n_stats_added, n_meta_added, n_duplicates_removed)."""
    if not html_path.exists():
        print(f"WARN: missing {html_path}", file=sys.stderr)
        return 0, 0, 0

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    stats_added = 0
    meta_added = 0
    dup_removed = 0

    for card in soup.select('div.entry-card[id^="item-"]'):
        kro_id = card.get("id", "").removeprefix("item-")
        data = items_data.get(kro_id)
        if not data:
            continue

        meta_ul = card.find("ul", class_="entry-meta")
        if meta_ul is None:
            continue

        # 1) entry-stats
        stats_raw = data.get("stats_raw") or []
        existing_stats = card.find("ul", class_="entry-stats")
        if stats_raw and existing_stats is None:
            new_ul = soup.new_tag("ul")
            new_ul["class"] = "entry-stats"
            for raw in stats_raw:
                if not isinstance(raw, str) or not raw.strip():
                    continue
                li = soup.new_tag("li")
                li.string = translate_stat_line(raw)
                new_ul.append(li)
            if new_ul.find("li") is not None:
                # insert immediately after meta_ul
                meta_ul.insert_after(NavigableString("\n  "))
                meta_ul.find_next_sibling()  # noop
                meta_ul.insert_after(new_ul)
                stats_added += 1

        # 2) weight/def/slots — only add fields not already present anywhere
        # in the meta. We assemble a single new <li> with just the missing
        # fields so we don't duplicate data that's already in the prose.
        weight = data.get("weight")
        defense = data.get("def")
        slots = data.get("slots")

        meta_text = meta_ul.get_text(" ", strip=True)
        extra_parts: list[str] = []
        if weight is not None and not meta_has_weight(meta_text):
            extra_parts.append(f"<strong>Gewicht:</strong> {weight}")
        if defense is not None and not meta_has_def(meta_text):
            extra_parts.append(f"<strong>DEF:</strong> {defense}")
        if slots is not None and slots > 0 and not meta_has_slots(meta_text):
            extra_parts.append(f"<strong>Slots:</strong> {slots}")

        if extra_parts:
            new_li = BeautifulSoup(f"<li>{' · '.join(extra_parts)}</li>", "html.parser").li
            if new_li is not None:
                meta_ul.append(new_li)
                meta_added += 1

        dup_removed += cleanup_duplicate_meta_li(meta_ul)

    html_path.write_text(str(soup), encoding="utf-8", newline="\n")
    return stats_added, meta_added, dup_removed


# ---------------------------------------------------------------------------
# Monsters
# ---------------------------------------------------------------------------


def enrich_monsters(html_path: Path, monsters_data: dict[str, dict]) -> int:
    if not html_path.exists():
        print(f"WARN: missing {html_path}", file=sys.stderr)
        return 0

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    enriched = 0

    cards = soup.select('div.entry-card[id^="mob-"], div.entry-card[id^="monster-"]')
    for card in cards:
        card_id = card.get("id", "")
        if card_id.startswith("mob-"):
            kro_id = card_id.removeprefix("mob-")
        else:
            kro_id = card_id.removeprefix("monster-")
        data = monsters_data.get(kro_id)
        if not data:
            continue

        existing_stats = card.find("ul", class_="entry-stats")
        if existing_stats is not None:
            continue

        bits: list[str] = []
        if data.get("level") is not None:
            bits.append(f"Lv {data['level']}")
        hp = fmt_int(data.get("hp"))
        if hp is not None:
            bits.append(f"HP {hp}")
        if data.get("def") is not None:
            bits.append(f"DEF {data['def']}")
        if data.get("mdef") is not None:
            bits.append(f"MDEF {data['mdef']}")
        if data.get("family"):
            bits.append(str(data["family"]))
        if data.get("property"):
            bits.append(str(data["property"]))
        if data.get("size"):
            bits.append(str(data["size"]))
        exp_base = fmt_int(data.get("exp_base"))
        exp_job = fmt_int(data.get("exp_job"))
        if exp_base is not None or exp_job is not None:
            bits.append(f"EXP {exp_base or '?'}/{exp_job or '?'}")

        if not bits:
            continue

        meta_ul = card.find("ul", class_="entry-meta")
        new_ul = soup.new_tag("ul")
        new_ul["class"] = "entry-stats"
        new_li = soup.new_tag("li")
        new_li.string = " · ".join(bits)
        new_ul.append(new_li)

        if meta_ul is not None:
            meta_ul.insert_after(new_ul)
        else:
            head = card.find("div", class_="entry-card-head")
            if head is not None:
                head.insert_after(new_ul)
            else:
                card.append(new_ul)
        enriched += 1

    html_path.write_text(str(soup), encoding="utf-8", newline="\n")
    return enriched


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main() -> int:
    items_data = load_json_dir(ITEMS_JSON_DIR)
    monsters_data = load_json_dir(MONSTERS_JSON_DIR)

    print(f"Loaded {len(items_data)} item JSONs, {len(monsters_data)} monster JSONs")

    items_html_ids = set()
    items_md_html_ids = set()

    for path, label in [(ITEMS_HTML, "items.html"), (ITEMS_MD_HTML, "items-md-equip.html")]:
        ids = re.findall(r'id="item-(\d+)"', path.read_text(encoding="utf-8"))
        bag = set(ids)
        if path == ITEMS_HTML:
            items_html_ids = bag
        else:
            items_md_html_ids = bag
        print(f"  {label}: {len(bag)} item cards")

    s1, m1, d1 = enrich_items(ITEMS_HTML, items_data)
    s2, m2, d2 = enrich_items(ITEMS_MD_HTML, items_data)
    mons = enrich_monsters(MONSTERS_HTML, monsters_data)

    missing_in_items = sorted(set(items_data) - items_html_ids)
    missing_in_md = sorted(set(items_data) - items_md_html_ids)

    print()
    print("=== SUMMARY ===")
    print(f"items.html         : +{s1} stats blocks, +{m1} meta lines, -{d1} duplicate meta lines")
    print(f"items-md-equip.html: +{s2} stats blocks, +{m2} meta lines, -{d2} duplicate meta lines")
    print(f"monster.html       : +{mons} stats blocks")
    print()
    print(f"Item JSON IDs not in items.html         ({len(missing_in_items)}): {missing_in_items}")
    print(f"Item JSON IDs not in items-md-equip.html ({len(missing_in_md)}): {missing_in_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
