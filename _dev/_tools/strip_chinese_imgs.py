#!/usr/bin/env python3
"""Strip every <img class="chinese-img"> element from all root HTML pages,
move the underlying image file to _dev/_archive/, and ensure the German
translated-table that follows the image becomes visible (open) by default.

Idempotent: re-running on already-cleaned pages is a no-op.
"""
from __future__ import annotations
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ARCHIVE = ROOT / "_dev" / "_archive" / "images"

IMG_RE = re.compile(
    r'<img\s+class="chinese-img(?:\s+[^"]+)?"[^>]*src="(images/[^"]+)"[^>]*>',
    re.IGNORECASE,
)
# Also catch caption span pattern
CAPTION_RE = re.compile(
    r'\s*<span class="img-caption">[^<]*</span>',
    re.IGNORECASE,
)
# <details class="translated-table"> ... </details> — make it default-open + un-toggle the markup
DETAILS_RE = re.compile(
    r'<details\s+class="translated-table">(.*?)</details>',
    re.IGNORECASE | re.DOTALL,
)
# Inside details, drop the <summary> and unwrap the rest into a div
SUMMARY_RE = re.compile(r'<summary>.*?</summary>', re.IGNORECASE | re.DOTALL)


def archive_image(rel_path: str) -> bool:
    """Move <repo>/<rel_path> → <repo>/_dev/_archive/<rel_path>. Return True if moved."""
    src = ROOT / rel_path
    if not src.exists():
        return False
    dest = ARCHIVE / rel_path[len("images/"):] if rel_path.startswith("images/") else ARCHIVE / Path(rel_path).name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return True


def replace_details_with_visible_block(html: str) -> str:
    """For each <details class="translated-table">, drop the <summary> and
    convert the surrounding wrapper into a visible block."""
    def repl(m: re.Match) -> str:
        inner = m.group(1)
        inner = SUMMARY_RE.sub("", inner)
        return f'<div class="translated-table-block">{inner}</div>'
    return DETAILS_RE.sub(repl, html)


def process(page: Path) -> tuple[int, int]:
    html = page.read_text(encoding="utf-8")
    img_count = 0
    archived_count = 0

    for m in IMG_RE.finditer(html):
        img_count += 1
        if archive_image(m.group(1)):
            archived_count += 1

    new_html = IMG_RE.sub("", html)
    new_html = CAPTION_RE.sub("", new_html)
    new_html = replace_details_with_visible_block(new_html)
    # collapse runs of blank lines created by removals
    new_html = re.sub(r"\n{3,}", "\n\n", new_html)

    if new_html != html:
        page.write_text(new_html, encoding="utf-8")
    return img_count, archived_count


def main() -> None:
    pages = sorted(ROOT.glob("*.html"))
    total_imgs = total_archived = pages_changed = 0
    for p in pages:
        imgs, arch = process(p)
        if imgs:
            total_imgs += imgs
            total_archived += arch
            pages_changed += 1
            print(f"  {p.name}: stripped {imgs} chinese-img, archived {arch} files")
    print(f"\n{pages_changed} pages changed · {total_imgs} chinese-img stripped · {total_archived} image files archived")


if __name__ == "__main__":
    main()
