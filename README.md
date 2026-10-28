# What To Ask For: build tooling

This branch (`tooling`) holds the generator, source data and checks for
https://mystickcal.github.io/what-to-ask-for/. The live site is the `main` branch
(GitHub Pages, deploy from branch, no Actions). Commits here never change the live site.

Rebuilt on 2026-10-28 from the published output after the original build folder was lost.
`python3 build.py` reproduced main at 561fe45 byte-for-byte (all 208 files), and the
live site matched that build byte-for-byte.

## Layout
- `data/site.json`: site name, updated date, category order, chip labels, `sitemap` flag.
- `data/entries.json`: one record per entry, in category order. `page`, `json` and
  `category_name` are derived by the build. `derek_checked` (optional) sets the date in
  the "How Derek runs it" source line; it defaults to `updated`.
- `static/`: copied as-is (app.js has the signup handler and search; do not edit the signup part).
- `build.py`: writes index.html, 404.html, e/<id>/index.html, api/<id>.json, entries.json, llms.txt, sitemap.xml.
- `extract_from_site.py`: the one-time recovery script (published site -> data/).
- `checks/sitecheck.py`: HTTP checks (200s, 404, OG tags, internal links, pinned signup form
  and Umami tag, pinned app.js, api == entries.json, sitemap, no em/en dashes, optional byte compare).
- `checks/browsercheck.py`: Playwright checks (search finds every entry, chips, example buttons,
  signup errors shown with zero gateway requests; nothing is submitted).

## Release
```
git clone -b main https://github.com/mystickcal/what-to-ask-for.git site
python3 build.py --out site                       # regenerate
git -C site status --short                        # review what changed
python3 checks/sitecheck.py what-to-ask-for --local site --expect N
python3 checks/browsercheck.py what-to-ask-for --local site
git -C site commit -am "..." && git -C site push  # only after both pass
python3 checks/sitecheck.py what-to-ask-for --live --expect N --compare-dir site
python3 checks/browsercheck.py what-to-ask-for --live
```
Rules: keep the signup form, Umami tag and app.js signup code unchanged (the checks pin them).
No em or en dashes in public copy. Any "How Derek runs it" note must be checked against the
Custody Journal code; leave `how_derek_runs_it` null when there is nothing real to say.
