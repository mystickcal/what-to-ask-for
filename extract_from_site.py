#!/usr/bin/env python3
"""One-time recovery: rebuild data/ from a checkout of the published site.

Usage: python3 extract_from_site.py ../what-to-ask-for
Reads entries.json + index.html (category chip labels) and writes
data/site.json and data/entries.json. Derived fields (page, json,
category_name) are dropped because build.py computes them.
"""
import json, re, sys, pathlib, html

site = pathlib.Path(sys.argv[1])
here = pathlib.Path(__file__).parent
d = json.loads((site / "entries.json").read_text())
idx = (site / "index.html").read_text()
short = dict(re.findall(r'<a class="cat" href="#c-[^"]+" data-c="([^"]+)">([^<]+) <span>', idx))
cats = [{"id": c["id"], "name": c["name"], "short": html.unescape(short[c["id"]])} for c in d["categories"]]
entries = []
for e in d["entries"]:
    e = dict(e)
    for k in ("page", "json", "category_name"):
        e.pop(k)
    entries.append(e)
(here / "data").mkdir(exist_ok=True)
(here / "data/site.json").write_text(json.dumps({"name": d["name"], "updated": d["updated"], "categories": cats}, indent=2) + "\n")
(here / "data/entries.json").write_text(json.dumps(entries, indent=2) + "\n")
print(len(cats), "categories,", len(entries), "entries")
