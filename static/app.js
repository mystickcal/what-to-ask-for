(function () {
  "use strict";
  // Copy buttons
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var el = document.getElementById(btn.getAttribute("data-copy"));
      var text = el ? el.textContent : "";
      var done = function () { var old = btn.textContent; btn.textContent = "Copied"; setTimeout(function () { btn.textContent = old; }, 1500); };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done, function () { fallback(el); done(); });
      } else { fallback(el); done(); }
    });
  });
  function fallback(el) {
    var r = document.createRange(); r.selectNodeContents(el);
    var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
    try { document.execCommand("copy"); } catch (e) {}
  }

  // Signup: posts to the self-hosted newsletter gateway (double opt-in), same as SkillCheck.
  var form = document.getElementById("signup");
  if (form) {
    var note = document.getElementById("signup-note");
    var btn = form.querySelector("button[type='submit']");
    var OK = "Check your inbox to confirm";
    var ERR = "We could not send that signup. Try again in a moment.";
    var EMAIL = /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)+$/;
    var busy = false;
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      if (busy) return;
      var f = form.elements, email = f.email.value.trim();
      if (!EMAIL.test(email) || email.length > 254) { note.textContent = "Enter a valid email address."; f.email.focus(); return; }
      if (!f.consent.checked) { note.textContent = "Tick the box to agree to the weekly email."; f.consent.focus(); return; }
      busy = true; btn.disabled = true; note.textContent = "Sending";
      fetch(form.action, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ email: email, brand: form.getAttribute("data-brand"), source: form.getAttribute("data-source"), consent: true, company: f.company.value }),
        credentials: "omit", cache: "no-store", redirect: "error"
      }).then(function (r) {
        if (!r.ok) throw new Error("request_failed");
        var type = (r.headers.get("content-type") || "").toLowerCase();
        if (type.indexOf("json") >= 0) return r.json().then(function (p) { if (p && p.error) throw new Error("request_failed"); });
      }).then(function () { form.reset(); note.textContent = OK; }, function () { note.textContent = ERR; })
        .then(function () { busy = false; btn.disabled = false; });
    });
  }

  // Search and category browse (home page only)
  var q = document.getElementById("q");
  if (!q) return;
  var list = document.getElementById("results"), count = document.getElementById("count"), none = document.getElementById("none");
  var browse = document.getElementById("browse");
  var groups = Array.prototype.slice.call(document.querySelectorAll("#browse .group"));
  var chips = Array.prototype.slice.call(document.querySelectorAll("#cats .cat"));
  var STOP = "a an the to of for in on my i me is it and or how do does what when with without can get make let our we you your be at by from this that so".split(" ");
  var entries = [], cat = "", catNames = {};
  function norm(s) { return (s || "").toLowerCase().replace(/[^a-z0-9 ]+/g, " "); }
  function tokens(s) { return norm(s).split(/\s+/).filter(function (t) { return t && STOP.indexOf(t) < 0; }); }
  function stem(t) { return t.length > 4 ? t.replace(/(ing|ed|es|s)$/, "") : t; }
  function prep(x) {
    return { x: x, f: [
      [tokens(x.name), 6], [tokens(x.aliases.join(" ")), 5], [tokens(x.keywords.join(" ")), 4],
      [tokens(x.needs.join(" ")), 3], [tokens(x.category_name || ""), 2], [tokens(x.summary), 1]
    ], needs: x.needs.map(norm), name: norm(x.name + " " + x.aliases.join(" ")) };
  }
  function score(p, qt, qs) {
    var s = 0, hitAll = true;
    qt.forEach(function (t) {
      var st = stem(t), best = 0;
      p.f.forEach(function (fw) {
        fw[0].forEach(function (w) {
          var ws = stem(w);
          if (w === t || ws === st) best = Math.max(best, fw[1]);
          else if (t.length >= 3 && (w.indexOf(t) === 0 || ws.indexOf(st) === 0)) best = Math.max(best, fw[1] * 0.6);
        });
      });
      if (!best) hitAll = false;
      s += best;
    });
    if (qs.length > 3) {
      if (p.name.indexOf(qs) >= 0) s += 8;
      p.needs.forEach(function (n) { if (n.indexOf(qs) >= 0) s += 6; });
    }
    if (hitAll && qt.length > 1) s *= 1.25;
    return s;
  }
  function row(x, why) {
    var li = document.createElement("li"), a = document.createElement("a");
    a.href = x.page;
    var n = document.createElement("span"); n.className = "r-name"; n.textContent = x.name;
    var d = document.createElement("span"); d.className = "r-need"; d.textContent = "\u201c" + (why || x.needs[0]) + "\u201d";
    a.appendChild(n); a.appendChild(d); li.appendChild(a); return li;
  }
  function bestNeed(p, qt) {
    var best = p.x.needs[0], bs = -1;
    p.x.needs.forEach(function (n) { var nt = tokens(n).map(stem); var c = qt.filter(function (t) { return nt.some(function (w) { return w.indexOf(stem(t)) === 0; }); }).length; if (c > bs) { bs = c; best = n; } });
    return best;
  }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }
  function run() {
    var raw = q.value.trim(), qt = tokens(raw), qs = norm(raw).trim();
    chips.forEach(function (c) {
      if (c.getAttribute("data-c") === cat) c.setAttribute("aria-current", "true"); else c.removeAttribute("aria-current");
    });
    if (!qt.length) {
      list.hidden = true; list.innerHTML = ""; browse.hidden = false; none.hidden = true;
      var shown = 0;
      groups.forEach(function (g) {
        var on = !cat || g.getAttribute("data-c") === cat;
        g.hidden = !on;
        if (on) shown += g.querySelectorAll("li").length;
      });
      count.textContent = cat ? plural(shown, "entry", "entries") + " in " + (catNames[cat] || cat) : plural(entries.length, "entry", "entries") + " in " + groups.length + " categories";
    } else {
      var out = entries.filter(function (p) { return !cat || p.x.category === cat; })
        .map(function (p) { return [p, score(p, qt, qs)]; })
        .filter(function (r) { return r[1] >= 2; })
        .sort(function (a, b) { return b[1] - a[1]; });
      list.innerHTML = "";
      out.forEach(function (r) { list.appendChild(row(r[0].x, bestNeed(r[0], qt))); });
      list.hidden = false; browse.hidden = true;
      count.textContent = plural(out.length, "match", "matches") + (cat ? " in " + (catNames[cat] || cat) : "");
      none.hidden = out.length > 0;
    }
    var url = new URL(location.href);
    if (raw) url.searchParams.set("q", raw); else url.searchParams.delete("q");
    if (cat) url.searchParams.set("c", cat); else url.searchParams.delete("c");
    url.hash = "";
    history.replaceState(null, "", url);
  }
  chips.forEach(function (c) {
    c.addEventListener("click", function (ev) {
      ev.preventDefault();
      var v = c.getAttribute("data-c");
      cat = (v === cat) ? "" : v;
      run();
    });
  });
  fetch("entries.json").then(function (r) { return r.json(); }).then(function (d) {
    entries = d.entries.map(prep);
    (d.categories || []).forEach(function (c) { catNames[c.id] = c.name; });
    var params = new URL(location.href).searchParams;
    var init = params.get("q"), ic = params.get("c");
    if (ic && catNames[ic]) cat = ic;
    if (init) q.value = init;
    q.addEventListener("input", run);
    run();
    document.documentElement.setAttribute("data-search-ready", "1");
  });
  document.querySelectorAll(".ex").forEach(function (b) {
    b.addEventListener("click", function () { q.value = b.getAttribute("data-q"); cat = ""; run(); q.focus(); });
  });
})();
