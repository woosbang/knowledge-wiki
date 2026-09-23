"""위키 건강검진 — 사람이 읽는 리포트를 만든다.

여기서는 무엇도 자동으로 고치지 않는다. '봐야 할 것'만 모아준다.
중복 후보는 기계적 유사도로 거르고, 실제 판단은 AI(또는 사람)가 한다.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from . import config, extract, scan
from .build import load_taxonomy
from .models import Entry


def _shingles(text: str, n: int = 5) -> set[str]:
    """한국어에 단어 분리가 잘 듣지 않아 문자 n-gram 으로 비교한다."""
    normalized = re.sub(r"\s+", "", text)[:20000]
    if len(normalized) < n:
        return set()
    return {normalized[i : i + n] for i in range(0, len(normalized) - n, 3)}


def similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / min(len(a), len(b))  # 포함 관계(부분집합)도 잡아내기 위해 min 사용


def find_duplicate_candidates(entries: list[Entry], threshold: float = 0.28) -> list[dict[str, Any]]:
    cache: dict[str, set[str]] = {}
    for e in entries:
        data = extract.load_extracted(e.slug)
        cache[e.slug] = _shingles(data["text"]) if data else set()

    pairs: list[dict[str, Any]] = []
    slugs = [e.slug for e in entries]
    for i, a in enumerate(slugs):
        for b in slugs[i + 1 :]:
            score = similarity(cache[a], cache[b])
            if score >= threshold:
                pairs.append({"a": a, "b": b, "similarity": round(score, 3)})
    return sorted(pairs, key=lambda p: -p["similarity"])


def _months_since(iso: str) -> int:
    if not iso:
        return 0
    try:
        then = date.fromisoformat(iso)
    except ValueError:
        return 0
    today = date.today()
    return (today.year - then.year) * 12 + (today.month - then.month)


def run() -> dict[str, Any]:
    taxonomy = load_taxonomy()
    rules = taxonomy.get("rules", {}) or {}
    stale_months = int(rules.get("stale_after_months", 12))
    split_threshold = int(rules.get("split_threshold", 12))
    misc_threshold = int(rules.get("misc_promote_threshold", 3))
    defined = {c["id"] for c in taxonomy.get("categories", [])}

    entries = scan.load_entries()
    unclassified = [e for e in entries if e.needs_classification]
    undefined_cat = [e for e in entries if e.category and e.category not in defined]
    stale = [e for e in entries if _months_since(e.doc_date) >= stale_months and e.status == "active"]
    flagged = [e for e in entries if e.status in ("outdated", "superseded")]
    duplicates = find_duplicate_candidates(entries)

    counts: dict[str, int] = {}
    for e in entries:
        counts[e.category or "misc"] = counts.get(e.category or "misc", 0) + 1
    oversized = [c for c, n in counts.items() if n >= split_threshold]
    misc_full = counts.get("misc", 0) >= misc_threshold

    # 고아: entries 는 남아있는데 docs/ 에서 원본이 사라진 경우
    orphans = [
        p.stem for p in config.ENTRIES_DIR.glob("*.json")
        if not (config.ROOT / Entry.load(p).source).exists()
    ]

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(entries),
        "unclassified": [e.slug for e in unclassified],
        "undefined_category": [(e.slug, e.category) for e in undefined_cat],
        "stale": [(e.slug, e.doc_date) for e in stale],
        "flagged": [(e.slug, e.status) for e in flagged],
        "duplicate_candidates": duplicates,
        "category_counts": counts,
        "oversized_categories": oversized,
        "misc_needs_promotion": misc_full,
        "orphans": orphans,
    }
    _write_markdown(report, entries)
    return report


def _write_markdown(r: dict[str, Any], entries: list[Entry]) -> None:
    by_slug = {e.slug: e for e in entries}
    title = lambda s: by_slug[s].title if s in by_slug else s  # noqa: E731

    lines = [
        "# 위키 건강검진 리포트",
        "",
        f"생성 시각: {r['generated_at']} · 문서 {r['total']}개",
        "",
        "> 이 파일은 `uv run wiki audit` 가 자동 생성한다. 직접 고치지 말 것.",
        "> 조치는 `wiki/entries/<slug>.json` 또는 `wiki/taxonomy.yaml` 을 수정해서 한다.",
        "",
        "## 1. 분류가 필요한 문서",
        "",
    ]
    if r["unclassified"]:
        lines += [f"- [ ] `{s}` — {title(s)}" for s in r["unclassified"]]
        lines += ["", "→ `/wiki-sync` 를 실행하거나 `uv run wiki classify` 로 처리."]
    else:
        lines.append("없음. 모든 문서가 분류되어 있다.")

    def verdict(a: str, b: str) -> str:
        """이미 관계가 기록된 쌍은 다시 검토하지 않도록 표시한다."""
        ea, eb = by_slug.get(a), by_slug.get(b)
        if not ea or not eb:
            return "⬜ 미검토"
        if ea.superseded_by == b or eb.superseded_by == a:
            return "✅ 대체 관계 기록됨"
        if b in ea.related or a in eb.related:
            return "✅ 관련 문서로 연결됨"
        if any(o.get("slug") == b for o in ea.overlaps) or any(
            o.get("slug") == a for o in eb.overlaps
        ):
            return "✅ 겹침 기록됨"
        return "⬜ 미검토"

    lines += ["", "## 2. 중복 의심 쌍", ""]
    if r["duplicate_candidates"]:
        lines.append("| 유사도 | 문서 A | 문서 B | 판단 |")
        lines.append("|---|---|---|---|")
        for p in r["duplicate_candidates"]:
            lines.append(
                f"| {p['similarity']:.2f} | `{p['a']}` {title(p['a'])} "
                f"| `{p['b']}` {title(p['b'])} | {verdict(p['a'], p['b'])} |"
            )
        lines += [
            "",
            "판단 기준: 한쪽이 다른 쪽의 상위 호환이면 구버전 entry 의 `status` 를 `superseded`,",
            "`superseded_by` 를 신버전 slug 로 설정한다. 서로 보완 관계면 `related` 로 연결한다.",
        ]
    else:
        lines.append("없음.")

    lines += ["", "## 3. 오래된 문서 (점검 권장)", ""]
    lines += [f"- `{s}` — {title(s)} (최종 {d})" for s, d in r["stale"]] or ["없음."]

    lines += ["", "## 4. outdated / superseded 표시된 문서", ""]
    lines += [f"- `{s}` — {title(s)} (`{st}`)" for s, st in r["flagged"]] or ["없음."]

    lines += ["", "## 5. 카테고리 현황", ""]
    for cat, n in sorted(r["category_counts"].items(), key=lambda kv: -kv[1]):
        mark = " ⚠ 분할 검토" if cat in r["oversized_categories"] else ""
        lines.append(f"- `{cat}`: {n}개{mark}")
    if r["misc_needs_promotion"]:
        lines += ["", "⚠ `misc` 에 문서가 쌓였다. 새 카테고리 신설을 검토할 것."]
    if r["undefined_category"]:
        lines += ["", "⚠ taxonomy.yaml 에 없는 카테고리를 쓰는 문서:"]
        lines += [f"- `{s}` → `{c}`" for s, c in r["undefined_category"]]

    if r["orphans"]:
        lines += ["", "## 6. 고아 entry (원본 HTML 이 사라짐)", ""]
        lines += [f"- `{s}`" for s in r["orphans"]]
        lines += ["", "→ 의도한 삭제라면 해당 entry json 을 지운다."]

    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.REPORTS_DIR / "health.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
