#!/usr/bin/env python3
"""Extract all unique English skill descriptions from klasse-*.html files."""
import re
import glob
import json

pairs = []
for fp in sorted(glob.glob('/home/trusch/rozero/klasse-*.html')):
    with open(fp, encoding='utf-8') as f:
        text = f.read()
    # find blocks: <h5>NAME ... </h5> ... <p class="skill-desc">DESC</p>
    blocks = re.findall(
        r'<h5>([^<]+?)\s*<span class="skill-tag">[^<]*</span>\s*</h5>\s*<p class="skill-prereq">[^<]*</p>\s*<p class="skill-desc">(.*?)</p>',
        text, re.DOTALL)
    for name, desc in blocks:
        pairs.append((name.strip(), desc.strip()))

# unique
unique = {}
for name, desc in pairs:
    if desc not in unique:
        unique[desc] = name

print(f'TOTAL: {len(pairs)} | UNIQUE: {len(unique)}')
out = [{'name': n, 'desc': d} for d, n in unique.items()]
with open('/home/trusch/rozero/_tools/_unique_descs.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
