#!/usr/bin/env python3
"""Browser checks (Playwright + Chromium) for What To Ask For and How It Plays.

  python3 checks/browsercheck.py SITE --local BUILD_DIR      # serve the build locally and check it
  python3 checks/browsercheck.py SITE --live                 # check the live site

Both sites: every page loads with no console errors; the signup form shows the
"bad email" and "no consent" errors and sends NOTHING (requests to the gateway are
blocked and counted; the check fails if any is attempted). Nothing is ever submitted.
what-to-ask-for: search finds each entry from its first "need" phrase (top 3), the
example buttons return matches, category chips filter, ?q= works.
how-it-plays: every demo mounts; for every demo the on/off toggle measurably changes
the simulated session (demo.simulate with scripted inputs, on vs off, deterministic);
sliders rewrite the prompt; Space on the canvas does not scroll; feel chips and search work.
"""
import argparse, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from sitecheck import serve, ORIGIN  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

GATEWAY = "newsletter.clickconsultants.com/v1/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

# Scripted input sessions for demo.simulate(driver, frames). Each returns the keys held on frame f.
DRIVERS = {
    "run_jump_hold": "function(d,f){return {right:true, jump:(f%45)<22};}",
    "run_jump_tap": "function(d,f){return {right:true, jump:(f%30)<2};}",
    "attack_spam": "function(d,f){return {attack:(f%10)<1};}",
    "attack_fast": "function(d,f){return {attack:(f%4)<1};}",
    "walk_attack": "function(d,f){return {right:(f%60)<30, attack:(f%8)<1};}",
    "dash_run": "function(d,f){return {right:true, dash:(f%40)<2, jump:(f%90)<10};}",
    "down_jump": "function(d,f){return {down:true, jump:(f%40)<3, right:(f%200)<60};}",
    "down_hold": "function(d,f){return {down:f>30};}",
    "idle": "function(d,f){return {};}",
    "zigzag": "function(d,f){return {right:(f%40)<20, left:(f%40)>=20};}",
    "left_run_jump": "function(d,f){return {left:true, jump:(f%50)<25};}",
    "jump_late": "function(d,f){return {right:true, jump:(f%24)>=20};}",
    "jump_wall": "function(d,f){var c=Math.floor(f/50)%2;return {right:c===0, left:c===1, jump:(f%25)<12};}",
    "coyote_late": "function(d,f){var p=d.player,dt=d.t-p.lastGround;return {right:true, jump:!p.grounded && !p.jumping && dt>40 && dt<90};}",
    "dash_spam": "function(d,f){return {right:true, dash:(f%6)<1};}",
    "roll_spam": "function(d,f){return {dash:(f%20)<1};}",
    "roll_walk": "function(d,f){return {right:(f%120)<60, left:(f%120)>=60, dash:(f%15)<1};}",
    "jump_short": "function(d,f){return {right:(f%120)<70, jump:(f%60)<5};}",
}


def run_page(page, url, errors):
    page.goto(url, wait_until="load")


def check_signup(page, fails, label):
    page.fill("#signup-email", "not-an-email")
    page.click("#signup button[type=submit]")
    if page.text_content("#signup-note").strip() != "Enter a valid email address.":
        fails.append(f"{label}: bad email message missing")
    page.fill("#signup-email", "sitecheck@example.com")
    if page.is_checked("#signup input[name=consent]"):
        page.uncheck("#signup input[name=consent]")
    page.click("#signup button[type=submit]")
    if page.text_content("#signup-note").strip() != "Tick the box to agree to the weekly email.":
        fails.append(f"{label}: consent message missing")
    page.fill("#signup-email", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site", choices=["what-to-ask-for", "how-it-plays"])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--local")
    g.add_argument("--live", action="store_true")
    ap.add_argument("--only", help="comma-separated ids to check (default all)")
    ap.add_argument("--report")
    a = ap.parse_args()
    base = serve(a.local, a.site) if a.local else f"{ORIGIN}/{a.site}/"
    fails, notes, gateway_calls, console = [], [], [], []
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(user_agent=UA, viewport={"width": 1100, "height": 900})

        def block(route):
            gateway_calls.append(route.request.url)
            route.abort()
        ctx.route("**/v1/subscriptions*", block)
        # keep analytics out of check runs
        ctx.route("**/u/script.js", lambda r: r.fulfill(status=200, content_type="text/javascript", body=""))
        page = ctx.new_page()
        cur = {"url": ""}
        page.on("console", lambda m: m.type == "error" and console.append((cur["url"], m.text)))
        page.on("pageerror", lambda e: console.append((cur["url"], str(e))))
        data = json.loads(page.request.get(base + "entries.json").body())
        ids = [x["id"] for x in data["entries"]]
        if a.only:
            ids = [i for i in ids if i in a.only.split(",")]

        def go(u):
            cur["url"] = u
            page.goto(u, wait_until="load")

        if a.site == "what-to-ask-for":
            go(base)
            page.wait_for_selector("html[data-search-ready='1']")
            check_signup(page, fails, "home")
            miss = 0
            for x in data["entries"]:
                if x["id"] not in ids:
                    continue
                page.fill("#q", x["needs"][0])
                top = page.eval_on_selector_all("#results li a", "els=>els.slice(0,3).map(e=>e.getAttribute('href'))")
                if x["page"] not in top:
                    miss += 1
                    fails.append(f"search '{x['needs'][0]}' -> top3 {top}, want {x['page']}")
            notes.append(f"search: {len(ids) - miss}/{len(ids)} entries found from their first need")
            page.fill("#q", "")
            for b in page.query_selector_all(".ex"):
                b.click()
                if page.eval_on_selector_all("#results li", "e=>e.length") == 0:
                    fails.append(f"example '{b.get_attribute('data-q')}' -> 0 results")
            page.fill("#q", "")
            for c in data["categories"]:
                page.click(f'.cat[data-c="{c["id"]}"]')
                vis = page.eval_on_selector_all("#browse .group:not([hidden]) li", "e=>e.length")
                if vis != c["count"]:
                    fails.append(f"chip {c['id']}: {vis} shown, want {c['count']}")
                page.click(f'.cat[data-c="{c["id"]}"]')
            go(base + "index.html?q=" + "emails go to spam")
            page.wait_for_selector("html[data-search-ready='1']")
            if page.eval_on_selector_all("#results li", "e=>e.length") == 0:
                fails.append("?q= gave no results")
            for i in ids:
                go(base + f"e/{i}/index.html")
                if not page.query_selector("#prompt") or not page.query_selector("button.copy"):
                    fails.append(f"{i}: prompt or copy button missing")
            check_signup(page, fails, ids[-1])
        else:
            go(base)
            check_signup(page, fails, "home")
            for f in data["feels"]:
                page.click(f'.feel[data-q="{f["feel"]}"]')
                got = page.eval_on_selector_all("#results li a", "els=>els.map(e=>e.getAttribute('href'))")
                if got != [f"e/{i}/index.html" for i in f["ids"]]:
                    fails.append(f"feel chip {f['feel']}: {got}")
                page.click(f'.feel[data-q="{f["feel"]}"]')
            for x in data["entries"]:
                if x["id"] not in ids:
                    continue
                page.fill("#q", x["name"])
                top = page.eval_on_selector_all("#results li a", "els=>els.slice(0,3).map(e=>e.getAttribute('href'))")
                if x["page"] not in top:
                    fails.append(f"search '{x['name']}' -> {top}")
            page.fill("#q", "")
            changed_by = {}
            for i in ids:
                go(base + f"e/{i}/index.html")
                try:
                    page.wait_for_selector("html[data-demo-ready='1']", timeout=10000)
                except Exception:
                    fails.append(f"{i}: demo did not mount")
                    continue
                res = page.evaluate("""(drivers) => {
                  const h = window.__hip, d = window.__demo, out = {};
                  for (const [name, src] of Object.entries(drivers)) {
                    const drv = eval('(' + src + ')');
                    h.cfg.apply(d.p, true, h.vals); const on1 = JSON.stringify(d.simulate(drv, 600));
                    const on2 = JSON.stringify(d.simulate(drv, 600));
                    h.cfg.apply(d.p, false, h.vals); const off = JSON.stringify(d.simulate(drv, 600));
                    h.cfg.apply(d.p, h.isOn(), h.vals);
                    out[name] = {deterministic: on1 === on2, differs: on1 !== off};
                  }
                  return out;
                }""", DRIVERS)
                det = all(v["deterministic"] for v in res.values())
                by = [k for k, v in res.items() if v["differs"] and v["deterministic"]]
                changed_by[i] = by
                if not by:
                    fails.append(f"{i}: toggle made no measurable difference (deterministic={det})")
                # sliders rewrite the prompt
                sl = page.query_selector_all("#sliders input[type=range]")
                if sl:
                    before = page.text_content("#prompt")
                    page.evaluate("""() => { const s = document.querySelector('#sliders input[type=range]');
                      const v = parseFloat(s.value), mx = parseFloat(s.max), mn = parseFloat(s.min);
                      s.value = String(v === mx ? mn : mx); s.dispatchEvent(new Event('input', {bubbles: true})); }""")
                    if page.text_content("#prompt") == before:
                        fails.append(f"{i}: first slider did not change the prompt")
                else:
                    fails.append(f"{i}: no sliders")
                # toggle button flips label and aria-pressed
                t0 = page.get_attribute("#toggle", "aria-pressed")
                page.click("#toggle")
                if page.get_attribute("#toggle", "aria-pressed") == t0:
                    fails.append(f"{i}: toggle button did not flip")
                # space on canvas does not scroll the page
                page.focus("#game")
                y0 = page.evaluate("scrollY")
                page.keyboard.press("Space")
                page.wait_for_timeout(50)
                if page.evaluate("scrollY") != y0:
                    fails.append(f"{i}: Space scrolled the page")
            notes.append(f"toggles: {sum(1 for v in changed_by.values() if v)}/{len(ids)} change behavior")
            check_signup(page, fails, ids[-1] if ids else "home")
            if a.report:
                pathlib.Path(a.report + ".drivers.json").write_text(json.dumps(changed_by, indent=1))
        go(base + "missing-page-browsercheck/")
        console[:] = [c for c in console if "missing-page-browsercheck" not in c[0] or "404" not in c[1]]
        br.close()
    for u, t in console:
        fails.append(f"console error on {u}: {t[:200]}")
    if gateway_calls:
        fails.append(f"signup made {len(gateway_calls)} gateway requests (should be 0)")
    notes.append(f"gateway requests: {len(gateway_calls)}")
    rep = {"site": a.site, "base": base, "fails": fails, "notes": notes}
    if a.report:
        pathlib.Path(a.report).write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps({"site": a.site, "base": base, "notes": notes}))
    print("FAILS:", len(fails))
    for f in fails[:60]:
        print("  -", f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
