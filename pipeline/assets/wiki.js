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

  // ── 홈 카탈로그: 카테고리 칩 + 표 안 필터 (페이지 이동 없이) ──
  var libQ = document.getElementById("lib-q");
  if (libQ) {
    var chips = Array.prototype.slice.call(document.querySelectorAll(".lib-chips .chip"));
    var sections = Array.prototype.slice.call(document.querySelectorAll(".lib-section"));
    var empty = document.getElementById("lib-empty");
    var activeCat = "";
    var opened = {};   // 사용자가 직접 펼친 그룹 (검색어를 지워도 유지)

    function setOpen(groupId, open) {
      Array.prototype.forEach.call(
        document.querySelectorAll('.lib-row.is-sub[data-parent="' + groupId + '"]'),
        function (row) { row.classList.toggle("is-open", open); }
      );
      var btn = document.querySelector('.src-toggle[data-toggle="' + groupId + '"]');
      if (btn) btn.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function applyLib() {
      var q = libQ.value.trim().toLowerCase();
      var terms = q ? q.split(/\s+/) : [];
      var anyVisible = false;
      var autoOpen = {};   // 검색어가 원본 제목에 걸리면 그 그룹은 펼친다
      sections.forEach(function (sec) {
        var catOk = !activeCat || sec.dataset.cat === activeCat;
        var visibleRows = 0;
        Array.prototype.forEach.call(sec.querySelectorAll(".lib-row"), function (row) {
          var text = (row.dataset.text || "").toLowerCase();
          var ok = catOk && terms.every(function (t) { return text.indexOf(t) !== -1; });
          row.classList.toggle("is-hidden", !ok);
          if (ok) {
            visibleRows++;
            if (terms.length && row.dataset.parent) autoOpen[row.dataset.parent] = true;
          }
        });
        sec.classList.toggle("is-hidden", !catOk || visibleRows === 0);
        if (catOk && visibleRows) anyVisible = true;
      });
      Array.prototype.forEach.call(document.querySelectorAll(".src-toggle"), function (btn) {
        var id = btn.dataset.toggle;
        setOpen(id, !!(opened[id] || autoOpen[id]));
      });
      if (empty) empty.hidden = anyVisible;
    }

    Array.prototype.forEach.call(document.querySelectorAll(".src-toggle"), function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.dataset.toggle;
        opened[id] = btn.getAttribute("aria-expanded") !== "true";
        setOpen(id, opened[id]);
      });
    });

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        activeCat = chip.dataset.cat || "";
        chips.forEach(function (c) { c.classList.toggle("is-active", c === chip); });
        applyLib();
        var target = activeCat && document.getElementById("lib-cat-" + activeCat);
        if (target) target.scrollIntoView({ block: "start", behavior: "smooth" });
      });
    });
    libQ.addEventListener("input", applyLib);
    libQ.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { libQ.value = ""; applyLib(); libQ.blur(); }
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

    // 같은 점수면 토픽(정돈본)이 원본 문서보다 앞에 온다
    hits.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return (a.doc.kind === "topic" ? 0 : 1) - (b.doc.kind === "topic" ? 0 : 1);
    });

    panel.innerHTML = hits.map(function (h) {
      var d = h.doc;
      var isTopic = d.kind === "topic";
      var dir = isTopic ? "t/" : "d/";
      var meta = [d.category, (d.tags || []).slice(0, 3).join(", ")].filter(Boolean).join(" · ");
      return '<a href="' + base + dir + encodeURIComponent(d.slug) + '.html">' +
             '<span class="r-title">' +
               '<span class="r-kind' + (isTopic ? " is-topic" : "") + '">' + (isTopic ? "토픽" : "원본") + "</span>" +
               escapeHtml(d.title) + "</span>" +
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
