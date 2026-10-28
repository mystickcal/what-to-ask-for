#!/usr/bin/env python3
"""HTTP checks for the What To Ask For and How It Plays static sites.

  python3 checks/sitecheck.py SITE --local BUILD_DIR [--expect N]   # serve a build locally (GitHub Pages layout) and check it
  python3 checks/sitecheck.py SITE --live [--expect N] [--compare-dir DIR]  # check the live site; optionally byte-compare every file to DIR

SITE is what-to-ask-for or how-it-plays. Checks: every page and file returns 200
(home, entries both as /e/<id>/ and /e/<id>/index.html, api JSON, entries.json,
llms.txt, og.png, static assets, sitemap.xml); a missing URL returns 404 with the
site's 404.html; entry count; OG and Twitter tags on home and every entry; every
internal href/src resolves with 200; the signup form block and Umami tag are
byte-identical to the pinned copies on every page; signup JS unchanged; api/<id>.json
equals the entries.json record; sitemap lists exactly home plus every entry; no em
or en dashes in public files. Exit 1 on any failure. Writes a JSON report with --report.
"""
import argparse, hashlib, html, json, os, pathlib, re, sys, threading, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ORIGIN = "https://mystickcal.github.io"
SITES = {
    "what-to-ask-for": {
        "form_sha": "7e9fc27b9bd15c651e934f8af138dacd6433a493354394732b7044c248d34cf8",
        "umami": '<script defer src="https://newsletter.clickconsultants.com/u/script.js" data-website-id="65149a71-ae1c-4a4c-8e7f-010028241f58" data-domains="mystickcal.github.io" data-auto-track="false" onload="window.umami&&umami.track()"></script>',
        "pinned_files": {"app.js": "c6e9c0fef557a93e1b55a4779430b636bf9b2434b6c1871ab6fd8c1be482b5ea"},
        "static": ["style.css", "app.js", "og.png", "llms.txt", "entries.json", "404.html"],
    },
    "how-it-plays": {
        "form_sha": "f6826e50d4d97975dcd2f148c77c8f46dc712b285e701b2d2133f18eae9a37b0",
        "umami": '<script defer src="https://newsletter.clickconsultants.com/u/script.js" data-website-id="6ec24210-90f9-4e61-8b5c-74d3c45555bc" data-domains="mystickcal.github.io"></script>',
        "pinned_files": {"site.js": "048c650543a77ca6d74566268f4a19d1824066f55bd9346aa13d3b6f461e0a66"},
        "static": ["style.css", "site.js", "demo.js", "entries.js", "og.png", "llms.txt", "entries.json", "404.html"],
    },
}
OG_REQ = ["og:site_name", "og:title", "og:description", "og:url", "og:type", "og:image", "og:image:type", "og:image:width",
          "og:image:height", "og:image:alt", "twitter:card", "twitter:title", "twitter:description", "twitter:image", "twitter:image:alt"]
DASHES = re.compile("[\u2013\u2014]|&mdash;|&ndash;|&#821[12];|&#x201[34];", re.I)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 sitecheck"


def serve(build_dir, repo):
    root = pathlib.Path(build_dir).resolve()

    class H(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def translate_path(self, path):
            path = urllib.parse.urlsplit(path).path
            pre = f"/{repo}/"
            if path == f"/{repo}":
                path = pre
            if not path.startswith(pre):
                return str(root / "__nope__")
            return str(root / urllib.parse.unquote(path[len(pre):]))

        def send_error(self, code, message=None, explain=None):
            if code == 404:
                body = (root / "404.html").read_bytes()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                super().send_error(code, message, explain)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}/{repo}/"


def get(url, cache={}):
    if url in cache:
        return cache[url]
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = (r.status, r.read(), r.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as e:
        res = (e.code, e.read(), e.headers.get("Content-Type", ""))
    except Exception as e:
        res = (0, str(e).encode(), "")
    cache[url] = res
    return res


def metas(s):
    out = {}
    for m in re.finditer(r'<meta (?:property|name)="([^"]+)" content="([^"]*)">', s):
        out[m.group(1)] = html.unescape(m.group(2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site", choices=SITES)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--local")
    g.add_argument("--live", action="store_true")
    ap.add_argument("--expect", type=int)
    ap.add_argument("--compare-dir", help="byte-compare every fetched file with this directory")
    ap.add_argument("--report")
    a = ap.parse_args()
    cfg = SITES[a.site]
    canon = f"{ORIGIN}/{a.site}/"
    base = serve(a.local, a.site) if a.local else canon
    fails, notes = [], []

    def fail(msg):
        fails.append(msg)

    st, raw, _ = get(base + "entries.json")
    if st != 200:
        print("entries.json not reachable:", st)
        sys.exit(1)
    data = json.loads(raw)
    entries = data["entries"]
    ids = [x["id"] for x in entries]
    if data["count"] != len(entries):
        fail(f"entries.json count {data['count']} != {len(entries)} records")
    if a.expect is not None and len(entries) != a.expect:
        fail(f"expected {a.expect} entries, found {len(entries)}")
    notes.append(f"{len(entries)} entries")

    urls = [base, base + "index.html"] + [base + f for f in cfg["static"]]
    urls += [base + f"e/{i}/" for i in ids] + [base + f"e/{i}/index.html" for i in ids] + [base + f"api/{i}.json" for i in ids]
    st_sm, sm_raw, _ = get(base + "sitemap.xml")
    if st_sm == 200:
        urls.append(base + "sitemap.xml")
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(get, urls))
    for u in urls:
        if get(u)[0] != 200:
            fail(f"{u} -> {get(u)[0]}")

    # 404
    st, body, _ = get(base + "this-page-does-not-exist-sitecheck/")
    if st != 404:
        fail(f"missing page returned {st}, want 404")
    elif body != get(base + "404.html")[1]:
        fail("404 body is not 404.html")

    # pinned JS
    for f, sha in cfg["pinned_files"].items():
        if hashlib.sha256(get(base + f)[1]).hexdigest() != sha:
            fail(f"{f} changed (signup handler lives here; sha mismatch)")

    # per page checks
    pages = {base: (canon, "website")}
    for i in ids:
        pages[base + f"e/{i}/index.html"] = (canon + f"e/{i}/", "article")
    pages[base + "404.html"] = (None, None)
    internal = set()
    for u, (og_url, og_type) in pages.items():
        s = get(u)[1].decode("utf-8", "replace")
        forms = re.findall(r'<form class="signup".*?</form>', s, re.S)
        if len(forms) != 1 or hashlib.sha256(forms[0].encode()).hexdigest() != cfg["form_sha"]:
            fail(f"{u}: signup form missing or changed")
        if s.count(cfg["umami"]) != 1 or s.count("u/script.js") != 1:
            fail(f"{u}: Umami tag missing or changed")
        if og_url:
            m = metas(s)
            for k in OG_REQ:
                if not m.get(k):
                    fail(f"{u}: missing {k}")
            title = html.unescape(re.search(r"<title>(.*?)</title>", s).group(1))
            if m.get("og:url") != og_url:
                fail(f"{u}: og:url {m.get('og:url')} != {og_url}")
            if m.get("og:type") != og_type:
                fail(f"{u}: og:type {m.get('og:type')}")
            if m.get("og:image") != canon + "og.png" or m.get("twitter:image") != canon + "og.png":
                fail(f"{u}: og/twitter image")
            if m.get("og:title") != title or m.get("twitter:title") != title:
                fail(f"{u}: og/twitter title != <title>")
            if not (m.get("og:description") == m.get("description") == m.get("twitter:description")):
                fail(f"{u}: descriptions differ")
            if m.get("twitter:card") != "summary_large_image":
                fail(f"{u}: twitter:card")
        for ref in re.findall(r'(?:href|src)="([^"]+)"', s):
            ref = html.unescape(ref)
            if re.match(r"^(https?:|mailto:|#)", ref):
                if ref.startswith(canon):
                    internal.add(base + ref[len(canon):])
                continue
            full = urllib.parse.urljoin(u, ref).split("#")[0]
            if a.local and ref.startswith(f"/{a.site}/"):
                full = base + ref[len(f"/{a.site}/"):]
            internal.add(urllib.parse.urlsplit(full)._replace(query="").geturl())
        if DASHES.search(s):
            fail(f"{u}: em or en dash in page")
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(get, internal))
    for u in sorted(internal):
        if get(u)[0] != 200:
            fail(f"internal link {u} -> {get(u)[0]}")
    notes.append(f"{len(internal)} internal link targets")

    # home lists every entry once
    home = get(base)[1].decode()
    for i in ids:
        if home.count(f'href="e/{i}/index.html"') != 1:
            fail(f"home lists e/{i}/ {home.count(f'href=\"e/{i}/index.html\"')} times")
    # api == record
    for x in entries:
        st, raw, _ = get(base + f"api/{x['id']}.json")
        if st == 200 and json.loads(raw) != x:
            fail(f"api/{x['id']}.json differs from entries.json")
    for f in ("entries.json", "llms.txt"):
        if DASHES.search(get(base + f)[1].decode()):
            fail(f"{f}: em or en dash")
    llms = get(base + "llms.txt")[1].decode()
    for i in ids:
        if f"(e/{i}/index.html)" not in llms:
            fail(f"llms.txt missing {i}")
    # sitemap
    if st_sm == 200:
        locs = re.findall(r"<loc>([^<]+)</loc>", sm_raw.decode())
        want = [canon] + [canon + f"e/{i}/" for i in ids]
        if sorted(locs) != sorted(want) or len(locs) != len(set(locs)):
            fail(f"sitemap.xml lists {len(locs)} URLs, want exactly home + {len(ids)} entries")
        notes.append(f"sitemap {len(locs)} URLs")
    else:
        notes.append("no sitemap.xml")

    # byte compare
    if a.compare_dir:
        root = pathlib.Path(a.compare_dir)
        n = 0
        for p in sorted(root.rglob("*")):
            if p.is_dir() or ".git" in p.parts:
                continue
            rel = p.relative_to(root).as_posix()
            st, body, _ = get(base + rel)
            n += 1
            if st != 200 or body != p.read_bytes():
                fail(f"compare: {rel} live {st} differs from {a.compare_dir}")
        notes.append(f"byte-compared {n} files with {a.compare_dir}")

    rep = {"site": a.site, "base": base, "fails": fails, "notes": notes, "checked_urls": len(urls) + len(internal)}
    if a.report:
        pathlib.Path(a.report).write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps({k: rep[k] for k in ("site", "base", "notes", "checked_urls")}))
    print("FAILS:", len(fails))
    for f in fails[:50]:
        print("  -", f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
