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

  // Signup placeholder: not wired anywhere on purpose.
  var form = document.getElementById("signup");
  if (form) form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    // TODO(Derek): POST to the self-hosted Listmonk gateway once this origin is allowed.
    document.getElementById("signup-note").textContent = "Thanks. Signup isn't connected yet, so nothing was sent or saved.";
  });

  // Search (home page only)
  var q = document.getElementById("q");
  if (!q) return;
  var list = document.getElementById("results"), count = document.getElementById("count"), none = document.getElementById("none");
  var STOP = "a an the to of for in on my i me is it and or how do does what when with without can get make let our we you your be at by from this that so".split(" ");
  var entries = [];
  function norm(s) { return (s || "").toLowerCase().replace(/[^a-z0-9 ]+/g, " "); }
  function tokens(s) { return norm(s).split(/\s+/).filter(function (t) { return t && STOP.indexOf(t) < 0; }); }
  function stem(t) { return t.length > 4 ? t.replace(/(ing|ed|es|s)$/, "") : t; }
  function prep(x) {
    return { x: x, f: [
      [tokens(x.name), 6], [tokens(x.aliases.join(" ")), 5], [tokens(x.keywords.join(" ")), 4],
      [tokens(x.needs.join(" ")), 3], [tokens(x.summary), 1]
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
  function run() {
    var raw = q.value.trim(), qt = tokens(raw), qs = norm(raw).trim();
    var out;
    if (!qt.length) out = entries.map(function (p) { return [p, 1]; });
    else out = entries.map(function (p) { return [p, score(p, qt, qs)]; }).filter(function (r) { return r[1] >= 2; }).sort(function (a, b) { return b[1] - a[1]; });
    list.innerHTML = "";
    out.forEach(function (r) { list.appendChild(row(r[0].x, qt.length ? bestNeed(r[0], qt) : null)); });
    count.textContent = qt.length ? (out.length + (out.length === 1 ? " match" : " matches")) : (entries.length + " entries");
    none.hidden = out.length > 0;
    var url = new URL(location.href);
    if (raw) url.searchParams.set("q", raw); else url.searchParams.delete("q");
    history.replaceState(null, "", url);
  }
  fetch("entries.json").then(function (r) { return r.json(); }).then(function (d) {
    entries = d.entries.map(prep);
    var init = new URL(location.href).searchParams.get("q");
    if (init) q.value = init;
    q.addEventListener("input", run);
    run();
    document.documentElement.setAttribute("data-search-ready", "1");
  });
  document.querySelectorAll(".ex").forEach(function (b) {
    b.addEventListener("click", function () { q.value = b.getAttribute("data-q"); run(); q.focus(); });
  });
})();
