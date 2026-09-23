/* 검색 + 테마 토글. 외부 라이브러리 없이 동작한다. */
(function () {
  "use strict";

  // ── 테마 ──
  var toggle = document.getElementById("theme-toggle");
  try {
    var saved = localStorage.getItem("wiki-theme");
    if (saved) document.documentElement.setAttribute("data-theme", saved);
  } catch (e) { /* 프라이빗 모드 등 — 무시하고 시스템 테마를 따른다 */ }

  if (toggle) {
    toggle.addEventListener("click", function () {
      var root = document.documentElement;
      var current = root.getAttribute("data-theme");
      if (!current) {
        var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        current = prefersDark ? "dark" : "light";
      }
      var next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("wiki-theme", next); } catch (e) {}
    });
  }

  // ── 검색 ──
  var input = document.getElementById("q");
  var panel = document.getElementById("results");
  if (!input || !panel) return;

  // data-index 는 현재 페이지 기준 상대 경로("search-index.json" 또는 "../search-index.json").
  // 같은 접두사를 문서 링크에도 그대로 쓴다.
  var base = (input.dataset.index || "search-index.json").replace("search-index.json", "");
  var docs = null;
  var loading = false;
  var selected = -1;

  function load() {
    if (docs || loading) return;
    loading = true;
    fetch(input.dataset.index)
      .then(function (r) { return r.json(); })
      .then(function (data) { docs = data; loading = false; render(input.value); })
      .catch(function () { loading = false; });
  }

  function score(doc, terms) {
    var title = (doc.title || "").toLowerCase();
    var summary = (doc.summary || "").toLowerCase();
    var tags = (doc.tags || []).join(" ").toLowerCase();
    var body = (doc.body || "").toLowerCase();
    var total = 0;
    for (var i = 0; i < terms.length; i++) {
      var t = terms[i];
      var s = 0;
      if (title.indexOf(t) !== -1) s += 10;
      if (tags.indexOf(t) !== -1) s += 6;
      if (summary.indexOf(t) !== -1) s += 4;
      if (body.indexOf(t) !== -1) s += 1;
      if (s === 0) return 0;          // 모든 검색어가 어딘가에는 있어야 한다
      total += s;
    }
    return total;
  }

  function render(query) {
    var q = (query || "").trim().toLowerCase();
    if (!q) { panel.hidden = true; panel.innerHTML = ""; return; }
    if (!docs) { panel.hidden = false; panel.innerHTML = '<p class="empty">색인을 불러오는 중…</p>'; return; }

    var terms = q.split(/\s+/).filter(Boolean);
    var hits = [];
    for (var i = 0; i < docs.length; i++) {
      var s = score(docs[i], terms);
      if (s > 0) hits.push({ doc: docs[i], score: s });
    }
    hits.sort(function (a, b) { return b.score - a.score; });
    hits = hits.slice(0, 12);

    if (!hits.length) {
      panel.innerHTML = '<p class="empty">일치하는 문서가 없습니다.</p>';
      panel.hidden = false;
      return;
    }

    panel.innerHTML = hits.map(function (h) {
      var d = h.doc;
      var meta = [d.category, (d.tags || []).slice(0, 3).join(", ")].filter(Boolean).join(" · ");
      return '<a href="' + base + "d/" + encodeURIComponent(d.slug) + '.html">' +
             '<span class="r-title">' + escapeHtml(d.title) + "</span>" +
             '<span class="r-meta">' + escapeHtml(meta) + "</span></a>";
    }).join("");
    panel.hidden = false;
    selected = -1;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  input.addEventListener("focus", load);
  input.addEventListener("input", function () { render(input.value); });

  input.addEventListener("keydown", function (e) {
    var items = panel.querySelectorAll("a");
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!items.length) return;
      e.preventDefault();
      if (selected >= 0) items[selected].classList.remove("is-sel");
      selected = e.key === "ArrowDown"
        ? (selected + 1) % items.length
        : (selected - 1 + items.length) % items.length;
      items[selected].classList.add("is-sel");
      items[selected].scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter" && selected >= 0 && items[selected]) {
      window.location.href = items[selected].getAttribute("href");
    } else if (e.key === "Escape") {
      input.blur();
      panel.hidden = true;
    }
  });

  document.addEventListener("click", function (e) {
    if (!e.target.closest(".search-wrap")) panel.hidden = true;
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && document.activeElement !== input) {
      e.preventDefault();
      input.focus();
    }
  });
})();
