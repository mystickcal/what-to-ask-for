#!/usr/bin/env python3
"""What To Ask For static site generator (rebuilt 2026-10-28 from the live output).

Usage:
  python3 build.py --out ../what-to-ask-for      # write the site into a checkout of main
Source of truth: data/site.json + data/entries.json, static/ (copied as-is).
Generated: index.html, 404.html, e/<id>/index.html, api/<id>.json,
entries.json, llms.txt, sitemap.xml (only when site.json has "sitemap": true).
"""
import argparse, json, pathlib, shutil, html as H

ROOT = pathlib.Path(__file__).resolve().parent
BASE = "https://mystickcal.github.io/what-to-ask-for/"
SITE = "What To Ask For"
UMAMI = '<script defer src="https://newsletter.clickconsultants.com/u/script.js" data-website-id="65149a71-ae1c-4a4c-8e7f-010028241f58" data-domains="mystickcal.github.io" data-auto-track="false" onload="window.umami&&umami.track()"></script>'
OG_ALT = "What To Ask For: say what your app needs, get the name of the piece and a prompt for your coding agent. By @omgitsderek."
HOME_TITLE = "What To Ask For: backend building blocks, named and turned into prompts"
HOME_DESC = "Describe a need in plain words and find the backend building block, when you need it, ways to build it and a copy-paste prompt."
DEREK_SRC = "From the Custody Journal code and release runbook, read {date}."


def e(s):
    return H.escape(s, quote=True)


# Signup form: copied verbatim from the live site. Do not edit (gateway contract).
def footer(p):
    return f'''<footer class="foot">
  <form class="signup" id="signup" method="post" action="https://newsletter.clickconsultants.com/v1/subscriptions" data-brand="what-to-ask-for" data-source="what-to-ask-for-web" novalidate>
    <label for="signup-email">One building block a week, by email</label>
    <label class="hp" aria-hidden="true">Leave this blank <input name="company" type="text" tabindex="-1" autocomplete="off" maxlength="200"></label>
    <div class="signup-row">
      <input id="signup-email" type="email" name="email" maxlength="254" placeholder="you@example.com" autocomplete="email" required>
      <button type="submit">Sign up</button>
    </div>
    <label class="signup-check"><input name="consent" type="checkbox" value="true" required> <span>Weekly email about one new backend building block. Unsubscribe any time.</span></label>
    <p class="signup-note" id="signup-note" role="status" aria-live="polite"></p>
    <noscript><p class="signup-note">JavaScript is required to sign up on this page. <a href="https://newsletter.clickconsultants.com/subscription/form">Open the hosted form</a> and choose What To Ask For.</p></noscript>
  </form>
  <p class="made">Built by Derek Salyers &middot; <a href="https://x.com/omgitsderek">@omgitsderek on X</a> &middot; <a href="{p}llms.txt">llms.txt</a> &middot; <a href="{p}entries.json">entries.json</a></p>
</footer>
<script src="{p}app.js" defer></script>
</body>
</html>
'''


def og(title, desc, url, typ):
    t, d = e(title), e(desc)
    return f'''<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="{typ}">
<meta property="og:image" content="{BASE}og.png">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(OG_ALT)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{BASE}og.png">
<meta name="twitter:image:alt" content="{e(OG_ALT)}">
'''


def page(p, title, desc, body, ogtags=""):
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
{ogtags}<link rel="stylesheet" href="{p}style.css">
<link rel="alternate" type="text/plain" href="{p}llms.txt" title="llms.txt">
{UMAMI}

</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><a class="brand" href="{p}index.html">{SITE}</a></header>
<main id="main">
{body}
</main>
''' + footer(p)


def li(items):
    return "".join(f"<li>{e(x)}</li>" for x in items)


def entry_body(x, prev, nxt):
    ways = "\n".join(
        f'<li><h3>{e(w["title"])} <span class="cost">{e(w["cost"])}</span></h3>\n'
        f'<p>{e(w["how"])}</p><p class="trade"><strong>Tradeoff:</strong> {e(w["tradeoff"])}</p></li>'
        for w in x["ways"])
    derek = ""
    if x.get("how_derek_runs_it"):
        derek = f'''<aside class="derek" aria-label="How Derek runs it">
<h2>How Derek runs it</h2>
<p>{e(x["how_derek_runs_it"])}</p>
<p class="src">{e(DEREK_SRC.format(date=x.get("derek_checked", x["updated"])))}</p>
</aside>'''
    needs = "".join(f"<li>&ldquo;{e(n)}&rdquo;</li>" for n in x["needs"])
    links = "".join(f'<li><a href="{e(l["url"])}">{e(l["title"])}</a></li>' for l in x["links"])
    return f'''
<article class="entry">
  <p class="crumb"><a href="../../index.html">All entries</a> / <a href="../../index.html?c={x["category"]}">{e(x["category_name"])}</a></p>
  <h1>{e(x["name"])}</h1>
  <p class="aka">Also called: {e(", ".join(x["aliases"]))}</p>
  <p class="lead">{e(x["summary"])}</p>
  <div class="when">
    <section><h2>You need it when</h2><ul>{li(x["need_when"])}</ul></section>
    <section><h2>Skip it when</h2><ul>{li(x["skip_when"])}</ul></section>
  </div>
  <section><h2>Ways to build it</h2><ol class="ways">{ways}</ol></section>
  <section class="prompt-box">
    <div class="prompt-head"><h2 id="prompt-h">Prompt for your coding agent</h2><button type="button" class="copy" data-copy="prompt">Copy prompt</button></div>
    <p class="hint">Replace the [bracketed] parts. Works in Claude Code, Cursor or Codex.</p>
    <pre id="prompt" tabindex="0" aria-labelledby="prompt-h">{e(x["prompt"])}</pre>
  </section>
  <section><h2>If you skip it</h2><p>{e(x["if_you_skip_it"])}</p></section>
  {derek}
  <section><h2>People describe this as</h2><ul class="needs">{needs}</ul></section>
  <section><h2>Further reading</h2><ul class="links">{links}</ul></section>
  <p class="meta">Checked {x["updated"]}. Prices and free tiers change, so check the provider before you rely on one. JSON: <a href="../../api/{x["id"]}.json">api/{x["id"]}.json</a></p>
  <nav class="pn" aria-label="More entries"><a href="../{prev["id"]}/index.html">&larr; {e(prev["name"])}</a><a href="../{nxt["id"]}/index.html">{e(nxt["name"])} &rarr;</a></nav>
</article>
'''


def home_body(site, entries, cats):
    n = len(entries)
    chips = f'<a class="cat" href="#browse" data-c="" aria-current="true">All <span>{n}</span></a>' + "".join(
        f'<a class="cat" href="#c-{c["id"]}" data-c="{c["id"]}">{e(c["short"])} <span>{c["count"]}</span></a>' for c in cats)
    groups = []
    for c in cats:
        rows = "\n".join(
            f'<li><a href="e/{x["id"]}/index.html"><span class="r-name">{e(x["name"])}</span><span class="r-need">&ldquo;{e(x["needs"][0])}&rdquo;</span></a></li>'
            for x in entries if x["category"] == c["id"])
        groups.append(f'<section class="group" id="c-{c["id"]}" data-c="{c["id"]}" aria-labelledby="h-{c["id"]}"><h3 class="group-h" id="h-{c["id"]}">{e(c["name"])} <span class="group-n">{c["count"]}</span></h3>\n<ol class="results">\n{rows}\n</ol></section>')
    groups = "\n".join(groups)
    return f'''
<section class="hero">
  <h1>Say what your app needs. Get the name of the piece, and a prompt for your coding agent.</h1>
  <p class="lead">For the parts of an app nobody sees: jobs, payments, logins, email, uploads, AI calls. Each entry says when you need it, a few ways to build it, and a prompt with checks for Claude Code, Cursor or Codex.</p>
  <form class="search" role="search" onsubmit="return false">
    <label for="q" class="vh">Describe what you need</label>
    <input id="q" type="search" placeholder="e.g. send each user an email at a time they pick" autocomplete="off" spellcheck="false">
  </form>
  <p class="examples"><span>Try:</span> <button type="button" class="ex" data-q="the AI step takes 40 seconds">the AI step takes 40 seconds</button> <button type="button" class="ex" data-q="Stripe sent the event twice">Stripe sent the event twice</button> <button type="button" class="ex" data-q="emails go to spam">emails go to spam</button> <button type="button" class="ex" data-q="limit generations per user">limit generations per user</button></p>
</section>
<nav class="cats" id="cats" aria-label="Browse by category">{chips}</nav>
<section aria-labelledby="results-h">
  <h2 id="results-h" class="vh">Entries</h2>
  <p class="count" id="count" aria-live="polite">{n} entries in {len(cats)} categories</p>
  <ol class="results" id="results" hidden></ol>
  <div id="browse">
{groups}
  </div>
  <p class="none" id="none" hidden>No match. Try plainer words, like &ldquo;slow&rdquo;, &ldquo;twice&rdquo; or &ldquo;spam&rdquo;.</p>
</section>
'''


def llms(site, entries, cats):
    catlist = ", ".join(f'{c["id"]} ({c["name"]})' for c in cats)
    out = [f"# {SITE}", "",
           "> Backend building blocks for AI-built apps. Describe a need in plain words, get the name of the piece, when you need it, 2 to 3 ways to build it, and a copy-paste prompt with acceptance checks.", "",
           "Agents: fetch /entries.json for everything in one file (search the needs, aliases and keywords fields), or /api/<id>.json for one entry. Each entry page is plain HTML at /e/<id>/index.html.", "",
           f"Each entry in entries.json has a category field. Categories: {catlist}.", "", "## Entries", ""]
    for c in cats:
        out += [f'### {c["name"]}', ""]
        out += [f'- [{x["name"]}](e/{x["id"]}/index.html): {x["summary"]} JSON: api/{x["id"]}.json' for x in entries if x["category"] == c["id"]]
        out.append("")
    out += ["## Data", "", "- [entries.json](entries.json): all entries with prompts and checks", "",
            f'Updated {site["updated"]}. Built by Derek Salyers (https://x.com/omgitsderek).']
    return "\n".join(out) + "\n"


def published(x, catname):
    # key order matches the published JSON
    keys = ["id", "name", "category", "category_name", "aliases", "needs", "keywords", "summary", "need_when", "skip_when",
            "ways", "prompt", "acceptance_checks", "if_you_skip_it", "how_derek_runs_it", "links", "page", "json", "updated"]
    full = dict(x, category_name=catname, page=f'e/{x["id"]}/index.html', json=f'api/{x["id"]}.json')
    return {k: full[k] for k in keys}


def build(out):
    site = json.loads((ROOT / "data/site.json").read_text())
    src = json.loads((ROOT / "data/entries.json").read_text())
    cats = site["categories"]
    names = {c["id"]: c["name"] for c in cats}
    order = {c["id"]: i for i, c in enumerate(cats)}
    # entries stay grouped by category, in data order inside a category
    src = sorted(src, key=lambda x: order[x["category"]])
    ids = [x["id"] for x in src]
    assert len(ids) == len(set(ids)), "duplicate ids"
    for x in src:
        assert x["prompt"].endswith("\n".join(f"{i}. {c}" for i, c in enumerate(x["acceptance_checks"], 1))), x["id"] + ": prompt must end with the acceptance checks"
    for c in cats:
        c["count"] = sum(1 for x in src if x["category"] == c["id"])
    entries = [published(x, names[x["category"]]) for x in src]
    out = pathlib.Path(out)
    for f in (ROOT / "static").iterdir():
        shutil.copyfile(f, out / f.name)
    (out / "index.html").write_text(page("", HOME_TITLE, HOME_DESC, home_body(site, entries, cats), og(HOME_TITLE, HOME_DESC, BASE, "website")))
    nf = page("/what-to-ask-for/", "Not found: " + SITE, "Page not found",
              '<h1>Page not found</h1><p><a href="/what-to-ask-for/index.html">Back to all entries</a></p>')
    (out / "404.html").write_text(nf)
    (out / "api").mkdir(exist_ok=True)
    n = len(entries)
    for i, x in enumerate(entries):
        src_x = src[i]
        x_for_page = dict(x, derek_checked=src_x.get("derek_checked", x["updated"]))
        d = out / "e" / x["id"]
        d.mkdir(parents=True, exist_ok=True)
        title = f'{x["name"]}: {SITE}'
        (d / "index.html").write_text(page("../../", title, x["summary"], entry_body(x_for_page, entries[i - 1], entries[(i + 1) % n]),
                                          og(title, x["summary"], f'{BASE}e/{x["id"]}/', "article")))
        (out / "api" / f'{x["id"]}.json').write_text(json.dumps(x, indent=2))
    pub_cats = [{"id": c["id"], "name": c["name"], "count": c["count"]} for c in cats]
    (out / "entries.json").write_text(json.dumps({"name": site["name"], "updated": site["updated"], "count": n,
                                                  "categories": pub_cats, "entries": entries}, indent=2))
    (out / "llms.txt").write_text(llms(site, entries, cats))
    if site.get("sitemap"):
        urls = [BASE] + [f'{BASE}e/{x["id"]}/' for x in entries]
        lm = {BASE: site["updated"], **{f'{BASE}e/{x["id"]}/': x["updated"] for x in entries}}
        body = "".join(f"  <url><loc>{u}</loc><lastmod>{lm[u]}</lastmod></url>\n" for u in urls)
        (out / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n')
    print(f"built {n} entries in {len(cats)} categories -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    build(ap.parse_args().out)
